#!/usr/bin/env python3

# communication via internet and UDP
from socket import socket, gethostname, AF_INET, SOCK_DGRAM, timeout
from struct import unpack

# test host address
HOST_ADDRESS = ("127.0.0.1", 2303)
# default maximal query response timeout
DEFAULT_MAX_RESPONSE_TIMEOUT = None
# set default buffer size
DEFAUL_BUFFER_SIZE = 1400

# define requests
A2S_INFO = "ÿÿÿÿTSource Engine Query\0".encode("iso-8859-1")
A2S_PLAYER_PREFIX = "ÿÿÿÿU".encode("iso-8859-1")
A2S_PLAYER_CHALLENGE_POSTFIX = "ÿÿÿÿ".encode("iso-8859-1")

class Player:
	'''
	Player data storage object
	'''
	def __init__(self, name):
		self.name = name
		self.score = 0
		self.time = ""

class SteamServerQuery:
	'''
	Steam server query API for ArmA 3
	'''
	def __init__(self, server, address=(), maxResponseTimeout=DEFAULT_MAX_RESPONSE_TIMEOUT, bufferSize=DEFAUL_BUFFER_SIZE):
		self.server = server
		if not address:
			self.address = self.server.address
		else:
			self.address = address
		self.client = None
		self.response = b""
		self.maxResponseTimeout = maxResponseTimeout
		self.bufferSize = bufferSize
	
	def createClientSocket(self):
		'''
		creats a new client socket
		'''
		if self.client is None:
			client = socket(AF_INET, SOCK_DGRAM)
			client.settimeout(self.maxResponseTimeout)
			self.client = client
	def A2S_INFO(self):
		'''
		Updates server attributes name, map, mission and playerNumbers
		'''
		self.createClientSocket()
		# basic info query
		try:
			self.client.sendto(A2S_INFO , self.address)
			self.response, _ = self.client.recvfrom(self.bufferSize)
		except timeout:
			self.server.map = ""
			self.server.mission = ""
			self.server.playerNumbers = (0,0)
			self.server.playerList = []
			return(1)
		# get name
		idx_start = 1 + self.response.find(b"\x11")
		idx_end = self.response.find(b"\x00", idx_start)
		name = self.response[idx_start:idx_end]
		self.server.name = name.decode("iso-8859-1")
		# get map
		idx_start = 1 + idx_end
		idx_end = self.response.find(b"\x00", idx_start)
		map = self.response[idx_start:idx_end]
		self.server.map = map.decode("iso-8859-1")
		# get mission
		idx_start = 1 + self.response.find(b"\x00", idx_end+1)
		idx_end = self.response.find(b"\x00", idx_start)
		mission = self.response[idx_start:idx_end]
		self.server.mission = mission.decode("iso-8859-1")
		# get player numbers
		idx = 3 + self.response.find(b"\x00", idx_end)
		playerCount = int.from_bytes(self.response[idx:idx+1], byteorder="big")
		playerMaxCount = int.from_bytes(self.response[idx+1:idx+2], byteorder="big")
		self.server.playerNumbers = (playerCount,playerMaxCount)
		return(0)
	
	def A2S_PLAYER(self):
		'''
		Updates player data
		'''
		self.createClientSocket()
		# challenge query
		try:
			self.client.sendto(A2S_PLAYER_PREFIX + A2S_PLAYER_CHALLENGE_POSTFIX, self.address)
			self.response, _ = self.client.recvfrom(self.bufferSize)
		except timeout:
			self.server.playerList = []
			return(1)
		A2S_PLAYER_POSTFIX = self.response[5:]
		# player info query
		try:
			self.client.sendto(A2S_PLAYER_PREFIX + A2S_PLAYER_POSTFIX, self.address)
			self.response, _ = self.client.recvfrom(self.bufferSize)
		except timeout:
			self.server.playerList = []
			return(1)
		# exit when the response is repeated
		if(A2S_PLAYER_POSTFIX == self.response[5:]):
			self.server.playerList = []
			return(1)
		# get player data
		self.server.playerList = []
		idx_start = 1 + self.response.find(b"\x00")
		idx_max = len(self.response) - 1;
		while(idx_start <= idx_max):
			# get name
			idx_end = self.response.find(b"\x00", idx_start)
			# exit when date is incomplete
			if idx_end < 0:
				break
			name = self.response[idx_start:idx_end]
			player = Player(name.decode("iso-8859-1"))
			# get score
			idx = 1 + idx_end
			# exit when date is incomplete
			if idx+7 > idx_max:
				break
			player.score = int(self.response[idx])
			# get time
			seconds = unpack("f", self.response[idx+4:idx+8])[0]
			minutes, seconds = divmod(seconds, 60)
			hours, minutes = divmod(minutes, 60)
			player.time = "{:02}:{:02}".format(int(hours), int(minutes))
			# add player
			self.server.playerList.append(player)
			# get next player
			idx_start = idx+9
		return(0)

class ArmaServer:
	'''
	Server data storage object
	'''
	def __init__(self, address, **kwargs):
		self.address = address
		self.name = ""
		self.map = ""
		self.mission = ""
		self.playerList = []
		self.playerNumbers = (0,0)
		self.online = False
		ip, port = address
		self.query = SteamServerQuery(self, (ip, port+1), **kwargs)
	def updateInfo(self):
		# update basic info
		status1 = self.query.A2S_INFO()
		# update online status
		self.online = (status1 == 0)
		# update player info
		if(self.online):
			status2 = self.query.A2S_PLAYER()
		else:
			status2 = 1
		return(status1 | status2)
	def __str__(self):
		pass

if __name__ == "__main__":
	# test run
	AchillesPublicServer = ArmaServer(*HOST_ADDRESS)
	print(AchillesPublicServer.__dict__)
	for player in AchillesPublicServer.playerList:
		print(player.__dict__)
