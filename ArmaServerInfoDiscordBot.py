#!/usr/bin/env python3

import discord
from discord.ext import commands
import websockets
import asyncio
from arma_server_query import ArmaServer
import sys, re
import yaml
from operator import itemgetter
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
		self.arma_server = arma_server
		self.info_update_timeout = info_update_timeout
		self.channel = discord.Object(id=channel_id)
		try:
			with open(CHANNEL_FILE, "rb") as file:
				message_id = str(int.from_bytes(file.read(), byteorder="big"))
		except FileNotFoundError:
			message_id = ""
		self.message = discord.Object(id=message_id)
		
		# add background process
		self.loop.create_task(self.worker())
		
		# add event handlers
		@self.event
		async def on_ready():
			'''
			Executed when connected to Discord
			'''
			print("Logged in as", self.user.name)
		
	def run(self, *args, **kwargs):
		'''
		starts the bot
		'''
		return super().run(self.bot_token, *args, **kwargs)
	
	async def create_message(self, *args, **kwargs):
		return await super().send_message(self.channel, *args, **kwargs)
		
	async def update_message(self, *args, **kwargs):
		return await super().edit_message(self.message, *args, **kwargs)
	
	async def worker(self):
		'''
		Background process that updates the server status regularly
		'''
		await self.wait_until_ready()
		while(not self.is_closed):
			await self.send_status()
			await asyncio.sleep(self.info_update_timeout)
	
	async def send_status(self):
		embed, presence = self.get_status()
		try:
			await self.change_presence(**presence)
			try:
				self.message = await self.get_message(self.channel, self.message.id)
				await self.update_message(embed=embed)
			except discord.errors.NotFound:
				self.message = await self.create_message(embed=embed)
				with open(CHANNEL_FILE, "wb") as file:
					file.write(int(self.message.id).to_bytes(8, byteorder="big"))
		except discord.errors.HTTPException as message:
			perror("Discord HTTP error:", message)
	
	def get_status(self):
		server_info = self.arma_server.info()
		player_into_list = self.arma_server.players()
		presence = self.format_presence(server_info)
		embed = self.format_embed(server_info, player_into_list)
		return (embed, presence)
	
	def format_presence(self, server_info):
		presence = {"game": None, "status": "dnd"}
		if server_info:
			map = server_info["map"]
			if not map:
				map = "nowhere"
			bot_game = "Zeus on {map} ({player_count}/{player_limit})".format(**server_info)
			presence["game"] = discord.Game(name=bot_game)
			presence["status"] = "online";
		return presence
		
	def format_embed(self, server_info, player_info_list):
		underscore = 44*"─"
		if server_info:
			status = "Online"
			color = 0x43B581
		else:
			status = "Offline"
			color = 0xF04747
		server_info.setdefault("name", "Unknown Server Name")
		name = server_info["name"]
		embed = discord.Embed(title=name, description=underscore, color=color)
		currentTime = datetime.utcnow().strftime("%H:%M:%S")
		embed.add_field(name="Query Time:", value="{} (UTC)".format(currentTime), inline=False)
		embed.add_field(name="Status:", value=status, inline=False)
		embed.add_field(name="Address:", value="steam://connect/{}:{}".format(*self.arma_server.address), inline=False)
		server_info.setdefault("map", "nowhere")
		map = server_info["map"]
		embed.add_field(name="Map:", value=map, inline=False)
		server_info.setdefault("mission", "none")
		mission = server_info["mission"] 
		embed.add_field(name="Mission:", value=mission, inline=False)
		embed.add_field(name="Player Count:", value="{player_count}/{player_limit}".format(**server_info), inline=False)
		if len(player_info_list) > 0:		
			lines=["```py"]
			for player_info in sorted(player_info_list, key=itemgetter("name")):
				lines.append("• {name} ({time})".format(**player_info))
			lines.append("```")
			embed.add_field(name="Player List:", value="\n".join(lines), inline=False)
		return embed

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
	bot = ArmaServerInfoDiscordBot(config["discord_bot"]["token"], arma_server, command_prefix=COMMAND_PREFIX, channel_id=config["discord_bot"]["channel_id"], info_update_timeout=config["discord_bot"]["info_update_timeout"])
	print("Starting the bot...")
	try:
		while True:
			try:
				bot.run()
			# Captures ConnectionResetError, which is caused when Discord shuts down the Bot's connection
			except (ConnectionError, websockets.exceptions.ConnectionClosed) as message:
				perror("Discord connection error:", message)
				print("Restarting the bot...")
	except discord.errors.LoginFailure as message:
		perror("Discord login error:", message)
		sys.exit(1)
	except discord.ext.commands.errors.CommandNotFound as message:
		perror("Discord command error:", message)
		sys.exit(1)
	except KeyboardInterrupt:
		print("Bot is shutting down by request.")
		sys.exit(0)
