# -*- coding: utf-8 -*-
"""
Python Slack Bot class for use with the pythOnBoarding app
"""
import logging
import os
import message
import pickle

from slackclient import SlackClient
from dataMgr import app
from dataMgr import db
from dataMgr import TeamApproval

logging.basicConfig(level=logging.INFO)

""" Design Decision: One bot instance represents one authorized bot for the team """
class Bot(object):

	oauth = {"client_id": os.environ.get("CLIENT_ID"),
			 "client_secret": os.environ.get("CLIENT_SECRET"),
					  # Scopes provide and limit permissions to what our app
					  # can access. It's important to use the most restricted
					  # scope that your app will need.
			 "scope": "bot, chat:write:bot, users:read"}
	
	verification = os.environ.get("VERIFICATION_TOKEN")

	""" Instanciates a Bot object to handle Slack onboarding interactions."""
	def __init__(self):
		super(Bot, self).__init__()
		self.name = "event_api_bot"
		self.emoji = ":robot_face:"
		# When we instantiate a new bot object, we can access the app
		# credentials we set earlier in our local development environment.
	
		# NOTE: Python-slack requires a client connection to generate
		# an oauth token. We can connect to the client without authenticating
		# by passing an empty string as a token and then reinstantiating the
		# client with a valid OAuth token once we have one.
		self.client = SlackClient("")
		# We'll use this dictionary to store the state of each message object.
		# In a production envrionment you'll likely want to store this more
		# persistantly in  a database.
		self.messages = {}

		self.team_id = ""
		self.bot_token = ""
		self.bot_id = ""

	def get_team_id(self):
		return self.team_id

	def get_bot_token(self):
		return self.bot_token

	def get_bot_id(self):
		return self.bot_id

	""" Sets the authorization for the bot to the team, essentially initializes it"""
	def auth_this_bot(self, team_id, bot_token):
		logging.info("Attempting to auth the bot with: <"+team_id+"> and <"+bot_token+">")
		self.team_id = team_id
		self.bot_token = bot_token
		self.client = SlackClient(self.bot_token)

		### set the bot as present on Slack
		self.set_presence("auto")

		### find the bot id
		self.find_bot_id()

	""" Authenticate a new team """
	def auth_new_team(self, code):
		"""
		Authenticate with OAuth and assign correct scopes.
		Save a dictionary of authed team information in memory on the bot
		object.

		Parameters
		----------
		code : str
			temporary authorization code sent by Slack to be exchanged for an
			OAuth token

		"""
		# After the user has authorized this app for use in their Slack team,
		# Slack returns a temporary authorization code that we'll exchange for
		# an OAuth token using the oauth.access endpoint
		auth_response = self.client.api_call(
								"oauth.access",
								client_id=Bot.oauth["client_id"],
								client_secret=Bot.oauth["client_secret"],
								code=code
								)
		# To keep track of authorized teams and their associated OAuth tokens,
		# we will save the team ID and bot tokens to the global
		# authed_teams object
		for key, value in auth_response.items():
			logging.info("Key: "+str(key) +", Value: "+str(value))

		team_id = auth_response["team_id"]
		bot_token = auth_response["bot"]["bot_access_token"]
		#DataMgr.add_new_team_auth(team_id, bot_token)

		# Auth the current bot
		self.auth_this_bot(team_id, bot_token)
		
	def set_presence(self, presence):
		logging.info("Setting presence:" + str(presence))
		response = self.client.api_call("users.setPresence",
											presence=presence)
		logging.info("Result from set presence:", response)
		for key, value in response.items():
			logging.info("\tKey: "+str(key) +", Value: "+str(value))


		connect_resp = self.client.rtm_connect()
		logging.info("RTM connect response:")
		for key, value in response.items():
			logging.info("\tKey: "+str(key) +", Value: "+str(value))
		
		if connect_resp:
			logging.info("RTM connected OK!")
		else:
			logging.warning("RTM connection failed. Invalid Slack token or bot ID?")


	def find_bot_id(self):
		logging.info("Trying to get bot id for name: <"+self.name+">")
		api_call = self.client.api_call("users.list")
		if api_call.get('ok'):
			# retrieve all users so we can find our bot
			users = api_call.get('members')
			for user in users:
				if 'name' in user and user.get('name') == self.name:
					logging.info("Bot ID for '" + user['name'] + "' is " + user.get('id'))
					self.bot_id = user.get('id')
		else:
			logging.error("could not find bot user with the name " + self.name)

	def handle_message(self, slack_event):
		logging.info("Handling a slack event!")
		at_bot = "<@" + self.bot_id + ">"
		logging.info("At bot message signature: " + at_bot)
		for key, value in slack_event.items():
			logging.info("Key: "+str(key) +", Value: "+str(value))
			#respond only if direted at bot or in direct message channel and not by the bot

		channel = slack_event['event']['channel']
		
		message_text = ""
		if 'text' in slack_event['event']:
			message_text = slack_event['event']['text']

		if 'user' in slack_event['event']:
			creator_id = slack_event['event']['user']
			logging.info("Channel:"+channel+", Creator id:"+creator_id+", Message text:"+message_text)

			if slack_event['event']['type'] == "message":
				#Posted on direct channel with the bot and not by the bot
				if channel.startswith("D") and creator_id != self.bot_id and at_bot not in message_text:
					logging.info("On direct message channel and not at bot")
					self.post_message(channel, "Message on direct channel, but not at bot:" + message_text)
				#Posted by directly mentioning the bot
				elif channel.startswith("D") and creator_id != self.bot_id and at_bot in message_text:
					self.post_message(channel, "Message on direct channel and at bot:" + message_text)
				#Posted by directly mentioning the bot
				elif channel.startswith("C") and creator_id != self.bot_id and at_bot in message_text:
					self.post_message(channel, "Message on public channel and at bot:" + message_text)
				elif channel.startswith("C") and creator_id != self.bot_id and at_bot not in message_text:
					self.post_message(channel, "Message on public channel, but not at bot:" + message_text)
				else:
					self.post_message(channel, "No idea where the message came from:" + message_text)

	def get_users_in_team(self):
		logging.info("Getting a list of users in bot channel: "+self.team_id);
		response = self.client.api_call("users.list")
		
		#for key, value in response.items():
		#	logging.info("Key: "+str(key) +", Value: "+str(value))

		user_data = []
		logging.info("Is result OK?:" + str(response['ok']))
		if response['ok'] and 'members' in response:
			for member in response['members']:
				logging.info("Member <"+member['id']+">, name <"+str(member['name'])+">")
				user_data.append({	"id": member['id'], 
									"team_id": member['team_id'],
									"name": member['name']
									})
		return user_data
	
	def get_bot_channels(self):
		logging.info("Get the channels that the bot is a member of...")
		response = self.client.api_call("channels.list",
										exclude_archived=True,
										exclude_emembers=True)

		channel_ids = []
		logging.info("Is result OK?:" + str(response['ok']))
		if response['ok'] and 'channels' in response:
			for channel in response['channels']:
				logging.info("Channel <"+channel['id']+">, is member? <"+str(channel['is_member'])+">")
				#use this channel if member
				if channel['is_member']:
					channel_ids.append(channel['id'])
		return channel_ids

	def open_dm(self, user_id):
		new_dm = self.client.api_call("im.open", user=user_id)
		dm_id = new_dm["channel"]["id"]
		return dm_id

	def post_message(self, channel, text):
		logging.info("Sending a message to channel {}".format(channel))
		auth_token = self.bot_token

		logging.info("The authentication token:" + str(auth_token))
		post_message = self.client.api_call("chat.postMessage",
											token=auth_token,
											channel=channel,
											text=text)
		logging.info("Result from chat post message:", post_message)
		for key, value in post_message.items():
			logging.info("Key: "+str(key) +", Value: "+str(value))
		return post_message
