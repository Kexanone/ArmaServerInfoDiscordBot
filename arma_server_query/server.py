# communication via internet and UDP
from socket import socket, AF_INET, SOCK_DGRAM, timeout
from .query_types import *
from .default_params import *
import struct

class SteamServer:
	'''
	Description:
		Class for creating Steam server queries
	
	Parameters:
		address	<tuple>: the Steam server address which consists of:
			ip <str>: IPv4
			port <int>: Steam query port (four digit integer)
		**kwargs <any>: for setting instance attributes
	
	Attributes:
		client <socket.socket>:
		max_response_time <int|float>: maximal timeout for the response
		buffer_size <int>: buffer size for the query response
		
	'''
	def __init__(self, address, **kwargs):
		self.address = address
		kwargs.setdefault("max_response_time", MAX_RESPONSE_TIME)
		kwargs.setdefault("buffer_size", BUFFER_SIZE)
		kwargs.setdefault("client", socket(AF_INET, SOCK_DGRAM))
		self.__dict__.update(kwargs)
		self.client.settimeout(max_response_time)
	
	def A2S_info(self):
		'''
		Description:
			Returns the raw response of a A2S_INFO query
		
		Parameters:
			none
		
		Returns:
			response <bytes>: response of the query; empty when failed
		'''
		# data query
		try:
			self.client.sendto(A2S_INFO , self.address)
			response, _ = self.client.recvfrom(self.buffer_size)
		except timeout:
			return(b"")
		return(response)
	
	def A2S_players(self):
		'''
		Description:
			Returns the raw response of a A2S_PLAYER query
		
		Parameters:
			none
		
		Returns:
			response <bytes>: response of the query; empty when failed
		'''
		# challenge query
		try:
			self.client.sendto(A2S_PLAYER_PREFIX + A2S_PLAYER_CHALLENGE_POSTFIX, self.address)
			response, _ = self.client.recvfrom(self.buffer_size)
		except timeout:
			return(b"")
		A2S_PLAYER_POSTFIX = response[5:]
		# data query
		try:
			self.client.sendto(A2S_PLAYER_PREFIX + A2S_PLAYER_POSTFIX, self.address)
			response, _ = self.client.recvfrom(self.buffer_size)
		except timeout:
			return(b"")
		# exit when the response is repeated
		if(A2S_PLAYER_POSTFIX == response[5:]):
			return(b"")
		return(response)

class ArmaServer(SteamServer):
	'''
	Description:
		Class for creating Arma 3 server queries
	
	Parameters:
		address	<tuple>: the server address
			ip <str>: IPv4
			port <int>: Steam query port (four digit integer)
		**kwargs <any>: for setting instance attributes of the parent class
	
	Attributes:
		max_response_time <int|float> (optional): maximal timeout for the response
		buffer_size <int> (optional): buffer size for the query response
		client <socket.socket> (optional): client socket for the connection
	
	'''
	def __init__(self, address, **kwargs):
		super().__init__(address, **kwargs)
		
	def info(self):
		'''
		Description:
			Returns a dict from a response of a A2S_INFO query
		
		Parameters:
			none
		
		Returns:
			response <dict>: with the possible keys:
				name <str>: the name of the server
				map <str>: the name of the map
				mission <str>: the name of the mission
				player_numbers <tuple>: the name of the mission
					player_count <int>: # players on the server
					player_max_count <int>: player limit for the server
		'''
		# get the byte string response
		response = self.A2S_info()
		# convert response to a dictionary
		if response:
			data = {}
			# get name
			idx_start = 1 + response.find(b"\x11")
			idx_end = response.find(b"\x00", idx_start)
			name = response[idx_start:idx_end]
			data["name"] = name.decode("UTF-8")
			# get map
			idx_start = 1 + idx_end
			idx_end = response.find(b"\x00", idx_start)
			map = response[idx_start:idx_end]
			data["map"] = map.decode("UTF-8")
			# get mission
			idx_start = 1 + response.find(b"\x00", idx_end+1)
			idx_end = response.find(b"\x00", idx_start)
			mission = response[idx_start:idx_end]
			data["mission"] = mission.decode("UTF-8")
			# get player numbers
			idx = 3 + response.find(b"\x00", idx_end)
			player_count = int.from_bytes(response[idx:idx+1], byteorder="big")
			player_max_count = int.from_bytes(response[idx+1:idx+2], byteorder="big")
			data["player_numbers"] = (player_count, player_max_count)
			return(data)
		else:
			return({})

	def players(self):
		'''
		Description:
			Returns a dict from a response of a A2S_PLAYER query
		
		Parameters:
			none
		
		Returns:
			response <list> of <dict>, where each dict represents a player:
				name <str>: the name of the player
				score <str>: total score
				time <str>: the time since the player joined in the format hh:mm
		'''
		# get the byte string response
		response = self.A2S_players()
		# convert response to a dictionary
		if response:
			player_list = []
			idx_start = 1 + response.find(b"\x00")
			idx_max = len(response) - 1;
			while(idx_start <= idx_max):
				# get name
				idx_end = response.find(b"\x00", idx_start)
				# exit when date is incomplete
				if idx_end < 0:
					break
				name = response[idx_start:idx_end]
				player_data = {"name": name.decode("UTF-8")}
				# get score
				idx = 1 + idx_end
				# exit when date is incomplete
				if idx+7 > idx_max:
					break
				player_data["score"] = int(response[idx])
				# get time
				seconds = struct.unpack("f", response[idx+4:idx+8])[0]
				minutes, seconds = divmod(seconds, 60)
				hours, minutes = divmod(minutes, 60)
				player_data["time"] = "{:02}:{:02}".format(int(hours), int(minutes))
				# add player
				player_list.append(player_data)
				# get next player
				idx_start = idx+9
			return(player_list)
		else:
			return({})
