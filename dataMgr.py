# -*- coding: utf-8 -*-
"""
Python DataMgr class for handling persistent data storage
"""
import logging
import os
import message
import pickle

from flask import Flask, request, make_response, render_template
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy

logging.basicConfig(level=logging.INFO)


#### GLOBAL VARIABLES ####
team_bots = {}

app = Flask(__name__)

# Environment variables are defined in app.yaml.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URI']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

#### SMALL DATA MANAGEMENT CLASS ####
class DataMgr(object):

	authed_teams = {}

	#init loads the data
	def __init__(self):
		logging.info("Loading Data Manager...")

	@staticmethod
	def load_team_auths():
		logging.info("Retrieving all team authorization tokens")
		if os.path.exists('data.pkl'):
			logging.info("Loading teams and authorizations!!!")
			
			pkl_file = open('data.pkl', 'rb')
			DataMgr.authed_teams = pickle.load(pkl_file)
			pkl_file.close()
			
			for key, value in DataMgr.authed_teams.items():
				logging.info("Key: "+str(key) +", Value: "+str(value))

	@staticmethod
	def get_authed_teams():
		return DataMgr.authed_teams

	@staticmethod
	def add_new_team_auth(team_id, access_token):
		logging.info("Adding new team authorization team_id: <"+team_id+">, token: <"+access_token+">")
		DataMgr.authed_teams[team_id] = {"bot_token": access_token}

		logging.info("Saving to persistent storage")
		output = open('data.pkl', 'wb')
		pickle.dump(DataMgr.authed_teams, output)
		output.close()

	@staticmethod
	def get_team_auth(team_id):
		logging.info("Getting the auth token for team: <"+team_id+">")
		return DataMgr.authed_teams[team_id]["bot_token"]