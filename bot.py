import os
import json
from requests import get
from urllib import parse

import discord
from discord.ext import commands
from dotenv import load_dotenv

# -------------------- Setup --------------------

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RG_KEY = os.getenv('RG_KEY')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = commands.Bot(command_prefix='!', intents=intents)

accountURL = "https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}?api_key="+RG_KEY
summonerURL = "https://euw1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}?api_key="+RG_KEY
entryURL = "https://euw1.api.riotgames.com/lol/league/v4/entries/by-summoner/{id}?api_key="+RG_KEY

SOLO_TIER_TO_ROLE = {
    "CHALLENGER": -2,
    "GRANDMASTER": -4,
    "MASTER": -6,
    "DIAMOND": -8,
    "EMERALD": -10,
    "PLATINUM": -11,
    "GOLD": -12,
    "SILVER": -13,
    "BRONZE": -14,
    "IRON": -15,
}
FLEX_TIER_TO_ROLE = {
    "CHALLENGER": -3,
    "GRANDMASTER": -5,
    "MASTER": -7,
    "DIAMOND": -9,
}
UNRANKED_ROLE = -16
NO_LEAGUE_ROLE = -17

# -------------------- Commands --------------------

@client.command(help="To link your league account, so the bot can figure out your rank.",brief="To link your league account")
async def link(ctx: commands.Context, *param):
    # Error handling
    summoner = ' '.join(param)
    split = summoner.split('#')
    if len(split) != 2:
        await ctx.send(f'Please set the parameter of this command to the form: `name#tag`.')
        return
    response = get(accountURL.format(name=parse.quote(split[0].strip()), tag=split[1].strip()))
    if response.status_code != 200:
        await ctx.send(f"This summoner does not exist... Please check your `name` and `tag` again.")
        return
    
    # Get the already linked members and save the data to links.json
    with open("links.json", "r") as file:
        links = json.load(file)
    member = ctx.author
    key = str(member.id)
    summonerData = get(summonerURL.format(puuid=response.json()['puuid'])).json()
    entryData = get(entryURL.format(id=summonerData['id'])).json()
    links[key] = {}
    links[key]['id'] = summonerData['id']
    links[key]['name'] = summonerData['name']
    
    # Prepare message
    soloData, flexData = None, None
    for queueType in entryData:
        if "SOLO" in queueType['queueType']:
            soloData = queueType
        if "FLEX" in queueType['queueType']:
            flexData = queueType
    await member.remove_roles(*member.roles[1:])
    if len(entryData) == 0:
        await member.add_roles(member.guild.roles[UNRANKED_ROLE])
    message = ""
    if soloData != None:
        message += f"You have the current solo queue rank: `{soloData['tier'].title()} {soloData['rank']} {soloData['leaguePoints']} lp`"
        links[key]['solo'] = soloData['tier']+" "+soloData['rank']
        await member.add_roles(member.guild.roles[SOLO_TIER_TO_ROLE[soloData['tier']]])
    else:
        message += "You are unranked in solo queue..."
        links[key]['solo'] = "UNRANKED"
    if flexData != None:
        message += f"\nYou have the current flex queue rank: `{flexData['tier'].title()} {flexData['rank']} {flexData['leaguePoints']} lp`"
        links[key]['flex'] = flexData['tier']+" "+flexData['rank']
        if flexData['tier'] in FLEX_TIER_TO_ROLE:
            await member.add_roles(member.guild.roles[FLEX_TIER_TO_ROLE[flexData['tier']]])
        elif soloData == None:
            await member.add_roles(member.guild.roles[UNRANKED_ROLE])
    else:
        message += "\nYou are unranked in flex queue..."
        links[key]['flex'] = "UNRANKED"

    with open("links.json", "w") as file:
        json.dump(links, file)
    await ctx.send(f'You have linked to your league account: `{summoner}`\n'+message)

@client.command(help="To set your roles in the server and show your rank in chat.",brief="To set your roles")
async def getrank(ctx: commands.Context):
    # Get the already linked members
    with open("links.json", "r") as file:
        links = json.load(file)
    member = ctx.author
    if str(member.id) not in links:
        await ctx.send(f'You are not linked to your league account yet. You can link using `!link name#tag`.')
        return
    respone = get(entryURL.format(id=links[str(member.id)]['id']))
    if respone.status_code != 200:
        await ctx.send(f'Something is wrong with the currently linked league account. Try linking again using `!link name#tag`.')
        return
    entryData = respone.json()
    soloData, flexData = None, None
    for queueType in entryData:
        if "SOLO" in queueType['queueType']:
            soloData = queueType
        if "FLEX" in queueType['queueType']:
            flexData = queueType

    # Give the right roles
    await member.remove_roles(*member.roles[1:])
    if len(entryData) == 0:
        await member.add_roles(member.guild.roles[UNRANKED_ROLE])
    message = ""
    if soloData != None:
        message += f"You have the current solo queue rank: `{soloData['tier'].title()} {soloData['rank']} {soloData['leaguePoints']} lp`"
        await member.add_roles(member.guild.roles[SOLO_TIER_TO_ROLE[soloData['tier']]])
    else:
        message += "You are unranked in solo queue..."
    if flexData != None:
        message += f"\nYou have the current flex queue rank: `{flexData['tier'].title()} {flexData['rank']} {flexData['leaguePoints']} lp`"
        if flexData['tier'] in FLEX_TIER_TO_ROLE:
            await member.add_roles(member.guild.roles[FLEX_TIER_TO_ROLE[flexData['tier']]])
        elif soloData == None:
            await member.add_roles(member.guild.roles[UNRANKED_ROLE])
    else:
        message += "\nYou are unranked in flex queue..."
    await ctx.send(message)
        

# -------------------- Events --------------------
    
# TODO: Add the on join event for the No League? role.

@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    else:
        await client.process_commands(message)

@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")
    guild = client.guilds[0]

    # Get the already linked members
    with open("links.json", "r") as file:
        links = json.load(file)

    # Check what members are not linked and sets their role to unlinked
    for member in guild.members:
        if member.bot: continue
        if str(member.id) not in links:
            # await member.remove_roles(*member.roles[1:])
            # await member.add_roles(guild.roles[NO_LEAGUE_ROLE])
            print(f"- {member.name}, id: {member.id} is not in the list")

    with open("links.json", "w") as file:
        json.dump(links, file)

# -------------------- Run --------------------

client.run(DISCORD_TOKEN)