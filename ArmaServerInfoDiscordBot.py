#!/usr/bin/env python3

import discord
from discord.ext import commands
import asyncio
from arma_server_query import ArmaServer
import sys, re
import yaml
from operator import attrgetter
from datetime import datetime

# default discord parameters
INFO_UPDATE_TIMEOUT = 30
COMMAND_PREFIX = "!"

# file names
CONFIG_FILE = __file__[:-2] + "yaml"
CHANNEL_FILE = __file__[:-2] + "bin"

def perror(*args, sep=" ", **kwargs):
	'''
	print red colored message to stderr
	'''
	message = "\033[91m" + sep.join(map(str, args)) +  "\033[0m"
	print(message, file=sys.stderr, **kwargs)

class ArmaServerInfoDiscordBot(commands.Bot):
	'''
	Discord bot that updates the Arma server info
	'''
	def __init__(self, bot_token, arma_server, channel_id="", info_update_timeout=INFO_UPDATE_TIMEOUT, **kwargs):
		super().__init__(**kwargs)
		
		# set attributes
		self.bot_token = bot_token
		self.arma_server = ArmaServer
		self.info_update_timeout = info_update_timeout
		self.channel = discord.Object(id=channel_id)
		try:
			with open(STORAGE_FILE, "rb") as file:
				message_id = str(int.from_bytes(file.read(), byteorder="big"))
		except FileNotFoundError:
			message_id = ""
		self.message = discord.Object(id=message_id)
		
		# add background process
		self.loop.create_task(self.backgroundProcInfoUpdate())
		
		# add event handlers
		@self.event
		async def on_ready():
			'''
			Executed when connected to Discord
			'''
			print("Logged in as", self.user.name)
		
		@self.command()
		async def update():
			'''
			!update command: Posts server status
			'''
			self.ArmaServer.updateInfo()
			embed = self.returnLatestStatus()
			await self.send_status(embed=embed)
	
	def run(self, *args, **kwargs):
		'''
		starts the bot
		'''
		return super().run(self.bot_token, *args, **kwargs)
	
	async def send_status(self, *args, **kwargs):
		return await super().send_message(self.channel, *args, **kwargs)
		
	async def edit_status(self, *args, **kwargs):
		return await super().edit_message(self.message, *args, **kwargs)
	
	async def backgroundProcInfoUpdate(self):
		'''
		Background process that updates the server status regularly
		'''
		await self.wait_until_ready()
		while(not self.is_closed):
			# To Do: make updateInfo suspendable
			self.ArmaServer.updateInfo()
			if self.ArmaServer.online:
				map = self.ArmaServer.map if self.ArmaServer.map else "?"
				BotGame = "Zeus on {} ({}/{})".format(map, *self.ArmaServer.playerNumbers)
				await self.change_presence(game=discord.Game(name=BotGame), status="online")
			else:
				await self.change_presence(game=None, status="dnd")
			await self.postLatestStatus()
			await asyncio.sleep(self.infoUpdateTimeout)
	
	def returnLatestStatus(self):
		underscore = 44*"─"
		if self.ArmaServer.online:
			status = "Online"
			color = 0x43B581
		else:
			status = "Offline"
			color = 0xF04747
		name = self.ArmaServer.name if self.ArmaServer.name else "Unknown Server Name"
		embed = discord.Embed(title=name, description=underscore, color=color)
		currentTime = datetime.utcnow().strftime("%H:%M:%S")
		embed.add_field(name="Query Time:", value="{} (UTC)".format(currentTime), inline=False)
		embed.add_field(name="Status:", value=status, inline=False)
		embed.add_field(name="Address:", value="steam://connect/{}:{}".format(*self.ArmaServer.query.address), inline=False)
		map = self.ArmaServer.map if self.ArmaServer.map else "none" 
		embed.add_field(name="Map:", value=map, inline=False)
		mission = self.ArmaServer.mission if self.ArmaServer.mission else "none" 
		embed.add_field(name="Mission:", value=mission, inline=False)
		embed.add_field(name="Player Count:", value="{}/{}".format(*self.ArmaServer.playerNumbers), inline=False)
		if len(self.ArmaServer.playerList) > 0:		
			lines=["```py"]
			for player in sorted(self.ArmaServer.playerList, key=attrgetter("name")):
				lines.append("• {} ({})".format(player.name, player.time, player.score, ))
			lines.append("```")
			embed.add_field(name="Player List:", value="\n".join(lines), inline=False)
		return embed
	
	async def postLatestStatus(self):
		embed = self.returnLatestStatus()
		try:
			try:
				self.message = await self.get_message(self.channel, self.message.id)
				await self.edit_status(embed=embed)
			except discord.errors.NotFound:
				self.message = await self.send_status(embed=embed)
				with open(STORAGE_FILE, "wb") as file:
					file.write(int(self.message.id).to_bytes(8, byteorder="big"))
		except discord.errors.HTTPException as message:
			perror("Discord HTTP error:", message)

if __name__ == "__main__":
	# load configuration file
	with open(CONFIG_FILE, "r") as config_stream:
		try:
			config = yaml.load(config_stream)
		except yaml.YAMLError as error:
			perror("YAML parsing error:", error)
			sys.exit(1)
	# create instance of the Arma Server Query API
	arma_server = ArmaServer(config["arma_server"]["address"], max_response_time=config["arma_server"]["max_response_timeout"])
	# create and run the bot
	bot = ArmaServerInfoDiscordBot(config["discord_bot"]["token"], arma_server, command_prefix=COMMAND_PREFIX, channelId=config["discord_bot"]["channel_id"], infoUpdateTimeout=config["discord_bot"]["info_update_timeout"])
	try:
		bot.run()
	except discord.errors.LoginFailure as message:
		perror("Discord login error:", message)
	except discord.ext.commands.errors.CommandNotFound as message:
		perror("Discord command error:", message)
