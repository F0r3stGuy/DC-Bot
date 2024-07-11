import os
import json
import discord.ext.commands
from time import sleep
from requests import get
from urllib import parse
from colorama import Fore, Style

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import discord.ext

# -------------------- Setup --------------------

INFO = f"{Style.BRIGHT}{Fore.LIGHTBLUE_EX}INFO{Fore.RESET}{Style.NORMAL}\t"
WARN = f"{Style.BRIGHT}{Fore.LIGHTYELLOW_EX}WARN{Fore.RESET}{Style.NORMAL}\t"
ERR = f"{Style.BRIGHT}{Fore.LIGHTRED_EX}ERR!{Fore.RESET}{Style.NORMAL}\t"

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
TIER_TO_IMAGE = {
    "CHALLENGER": "https://static.wikia.nocookie.net/leagueoflegends/images/1/14/Season_2023_-_Challenger.png",
    "GRANDMASTER": "https://static.wikia.nocookie.net/leagueoflegends/images/6/64/Season_2023_-_Grandmaster.png",
    "MASTER": "https://static.wikia.nocookie.net/leagueoflegends/images/e/eb/Season_2022_-_Master.png",
    "DIAMOND": "https://static.wikia.nocookie.net/leagueoflegends/images/3/37/Season_2023_-_Diamond.png",
    "EMERALD": "https://static.wikia.nocookie.net/leagueoflegends/images/4/4b/Season_2023_-_Emerald.png",
    "PLATINUM": "https://static.wikia.nocookie.net/leagueoflegends/images/3/3b/Season_2022_-_Platinum.png",
    "GOLD": "https://static.wikia.nocookie.net/leagueoflegends/images/8/8d/Season_2022_-_Gold.png",
    "SILVER": "https://static.wikia.nocookie.net/leagueoflegends/images/c/c4/Season_2023_-_Silver.png",
    "BRONZE": "https://static.wikia.nocookie.net/leagueoflegends/images/e/e9/Season_2022_-_Bronze.png",
    "IRON": "https://static.wikia.nocookie.net/leagueoflegends/images/f/fe/Season_2022_-_Iron.png",
    "UNRANKED": "https://static.wikia.nocookie.net/leagueoflegends/images/3/3e/Season_2022_-_Unranked.png"
}

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RG_KEY = os.getenv('RG_KEY')

accountURL = "https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}?api_key="+RG_KEY
summonerURL = "https://euw1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}?api_key="+RG_KEY
entryURL = "https://euw1.api.riotgames.com/lol/league/v4/entries/by-summoner/{id}?api_key="+RG_KEY

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

# -------------------- Helpers --------------------

keysToRemove = []

async def handleApiDataAndMakeEmbed(links, member: discord.Member, embedTitle: str) -> tuple[discord.Embed, bool]:
    key = str(member.id)
    response = get(entryURL.format(id=links[str(member.id)]['id']))
    if response.status_code != 200:
        print(f"{ERR}{member.name} has a broken link. Removing from list...")
        keysToRemove.append(key)
        return (discord.Embed(description="Something is wrong with the currently linked league account. Try linking again using `link` command.", colour=discord.Colour.red()), True)
    entryData = response.json()
    soloData, flexData = None, None
    for queueType in entryData:
        if "SOLO" in queueType['queueType']:
            soloData = queueType
        if "FLEX" in queueType['queueType']:
            flexData = queueType
    
    # Give the right roles and prepare message
    embed = discord.Embed(title=embedTitle, colour=discord.Colour.blurple())
    embed.set_author(name=links[key]['name'])

    await member.remove_roles(*member.roles[1:])
    if len(entryData) == 0:
        await member.add_roles(member.guild.roles[UNRANKED_ROLE])
    if soloData != None:
        soloField = f"{soloData['tier'].title()} {soloData['rank']} {soloData['leaguePoints']} lp"
        links[key]['solo'] = soloData['tier']+" "+soloData['rank']
        await member.add_roles(member.guild.roles[SOLO_TIER_TO_ROLE[soloData['tier']]])
    else:
        soloField = "Unranked"
        links[key]['solo'] = "UNRANKED"
    if flexData != None:
        flexField = f"{flexData['tier'].title()} {flexData['rank']} {flexData['leaguePoints']} lp"
        links[key]['flex'] = flexData['tier']+" "+flexData['rank']
        if flexData['tier'] in FLEX_TIER_TO_ROLE:
            await member.add_roles(member.guild.roles[FLEX_TIER_TO_ROLE[flexData['tier']]])
        elif soloData == None:
            await member.add_roles(member.guild.roles[UNRANKED_ROLE])
    else:
        flexField = "Unranked"
        links[key]['flex'] = "UNRANKED"
    
    with open("links.json", "w") as file:
        json.dump(links, file, indent=4)
    
    embed.add_field(name=f"Solo/Duo Queue", value=soloField, inline=False)
    embed.add_field(name=f"Flex Queue", value=flexField, inline=False)
    embed.set_thumbnail(url=TIER_TO_IMAGE[links[key]['solo'].split(' ')[0]])
    return (embed, False)

# -------------------- Commands --------------------

@bot.tree.command(name="link", description="Links your league account to discord, so the bot can figure out your rank.")
@app_commands.describe(summoner="Your summoner name")
@app_commands.describe(tag="Your tag")
async def link(interaction: discord.Interaction, summoner: str, tag: str):
    # Error handling
    response = get(accountURL.format(name=parse.quote(summoner.strip()), tag=tag.strip()))
    if response.status_code != 200:
        embed = discord.Embed(description="This summoner does not exist... Please check your `name` and `tag` again.", colour=discord.Colour.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Get the already linked members
    with open("links.json", "r") as file:
        links = json.load(file)
    member = interaction.user
    key = str(member.id)
    response = get(summonerURL.format(puuid=response.json()['puuid']))
    if response.status_code != 200:
        embed = discord.Embed(description="This summoner does not exist... Please check your `name` and `tag` again.", colour=discord.Colour.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    summonerData = response.json()
    links[key] = {}
    links[key]['id'] = summonerData['id']
    links[key]['name'] = summoner+'#'+tag.upper()
    
    embed = await handleApiDataAndMakeEmbed(links, member, "Linked!")
    await interaction.response.send_message(embed=embed[0], ephemeral=embed[1])

@bot.tree.command(name="elo", description="Updates your roles in the server according to your rank.")
async def elo(interaction: discord.Interaction):
    # Get the already linked members
    with open("links.json", "r") as file:
        links = json.load(file)
    member = interaction.user
    if str(member.id) not in links:
        embed = discord.Embed(description="You are not linked to your league account yet. See the `link` command.", colour=discord.Colour.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = await handleApiDataAndMakeEmbed(links, member, "Ranks")
    await interaction.response.send_message(embed=embed[0], ephemeral=embed[1])        

# -------------------- Events --------------------
    
@bot.event
async def on_member_join(member: discord.Member):
    await member.add_roles(member.guild.roles[NO_LEAGUE_ROLE])
    dm: discord.DMChannel = await member.create_dm()
    embed = discord.Embed(title=f"Welcome {member.name}!", description="This bot manages the roles in the server, which correspond to the league of legends ranks.\n\nPlease link your league account to the server by using the '/link' command.\n(Preferably in the #bot-using channel)", color=discord.Colour.blurple())
    embed.set_footer(text="Thank you!")
    await dm.send(embed=embed)
    

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    else:
        await bot.process_commands(message)

@bot.event
async def on_ready():
    guild = bot.guilds[0]

    # Get the already linked members
    with open("links.json", "r") as file:
        links = json.load(file)

    # Check what members are not linked and sets their role to unlinked
    for member in guild.members:
        if member.bot: continue
        if str(member.id) not in links:
            print(f"{WARN}{member.name}, id: {member.id} is not in the list")

    # with open("links.json", "w") as file:
    #     json.dump(links, file)

    print(f"{INFO}{bot.user} is ready to go!")

async def on_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.CheckFailure):
        print(f"{WARN}{interaction.user.name} used the forbidden command: {Fore.MAGENTA}{interaction.command.name}{Fore.RESET}")
    else:
        print(error)
bot.tree.on_error = on_error

# -------------------- Modding --------------------

def check_if_it_is_me(interaction: discord.Interaction) -> bool:
    return interaction.user.id == 374582127515271168

@bot.tree.command(name="sync", description="Sync the bot commands globally.")
@app_commands.check(check_if_it_is_me)
async def sync(interaction: discord.Interaction):
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"{INFO}Synced {len(synced)} commands")
        await interaction.response.send_message(embed=discord.Embed(description="Synced!", colour=discord.Colour.blurple()))
    except Exception as e:
        print(e)
        await interaction.response.send_message(embed=discord.Embed(description="Synced failed", colour=discord.Colour.red()))

@bot.tree.command(name="set", description="Link someone else using their discord id.")
@app_commands.check(check_if_it_is_me)
async def set(interaction: discord.Interaction, dcid: str, summoner: str, tag: str):
    # Error handling
    response = get(accountURL.format(name=parse.quote(summoner.strip()), tag=tag.strip()))
    if response.status_code != 200:
        embed = discord.Embed(description="This summoner does not exist... Please check your `name` and `tag` again.", colour=discord.Colour.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Get the already linked members
    with open("links.json", "r") as file:
        links = json.load(file)
    response = get(summonerURL.format(puuid=response.json()['puuid']))
    if response.status_code != 200:
        embed = discord.Embed(description="This summoner does not exist... Please check your `name` and `tag` again.", colour=discord.Colour.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    summonerData = response.json()
    links[dcid] = {}
    links[dcid]['id'] = summonerData['id']
    links[dcid]['name'] = summoner+'#'+tag.upper()
    
    embed = await handleApiDataAndMakeEmbed(links, interaction.guild.get_member(int(dcid)), "Linked!")
    await interaction.response.send_message(embed=embed[0], ephemeral=embed[1])

@bot.tree.command(name="all", description="Update rank roles for all connected users.")
@app_commands.check(check_if_it_is_me)
async def all(interaction: discord.Interaction):
    await interaction.response.defer()
    with open("links.json", "r") as file:
        links = json.load(file)

    global keysToRemove
    
    for dcid in links:
        print(f"{INFO}{dcid}: {links[dcid]["name"]} is being updated")
        member = interaction.guild.get_member(int(dcid))
        if (member == None):
            keysToRemove.append(dcid)
            continue
        await handleApiDataAndMakeEmbed(links, member, "")
        sleep(0.06)

    for key in keysToRemove:
        links.pop(key)
    keysToRemove = []

    for member in interaction.guild.members:
        if member.bot: continue
        if str(member.id) not in links:
            await member.remove_roles(*member.roles[1:])
            await member.add_roles(interaction.guild.roles[NO_LEAGUE_ROLE])

    with open("links.json", "w") as file:
        json.dump(links, file, indent=4)

    await interaction.followup.send(embed=discord.Embed(description="Updated all the roles!", colour=discord.Colour.blurple()))

# -------------------- Run --------------------

bot.run(DISCORD_TOKEN)