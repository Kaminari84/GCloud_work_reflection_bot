# -*- coding: utf-8 -*-
"""
Python DataMgr class for handling persistent data storage
"""
import logging
import os
import message
#import pickle
import datetime

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

class TeamApproval(db.Model):
    id = db.Column(db.String(80), primary_key=True)
    authorization_token = db.Column(db.String(128))
    timestamp = db.Column(db.DateTime())

    def __init__(self, team_id, authorization_token, timestamp):
        self.id = team_id
        self.timestamp = timestamp
        self.authorization_token = authorization_token

class SurveyQuestionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime())
    user_id = db.Column(db.String(80)) 
    survey_id = db.Column(db.Integer)
    question_id = db.Column(db.Integer)
    question_type = db.Column(db.String(80))
    text = db.Column(db.Text)

    def __init__(self, user_id, survey_id, question_id, question_type, text):
        self.timestamp = datetime.datetime.utcnow()
        self.user_id = user_id
        self.survey_id = survey_id
        self.question_id = question_id
        self.question_type = question_type
        self.text = text

class SurveyQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    text = db.Column(db.String(256))

    def __init__(self, id, survey_id, text):
        self.id = id
        self.survey_id = survey_id
        self.text = text

class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    questions = db.relationship('SurveyQuestion', backref='survey', lazy=True)

    def __init__(self, id, name):
        self.id = id
        self.name = name

class SurveySchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer)
    week_day = db.Column(db.Integer)
    hour = db.Column(db.Integer)
    minute = db.Column(db.Integer)

    def __init__(self, id, survey_id, week_day, hour, minute):
        self.id = id
        self.survey_id = survey_id
        self.week_day = week_day
        self.hour = hour
        self.minute = minute

class ParticipantSurveyAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer)
    user_id = db.Column(db.String(80))

    def __init__(self, survey_id, user_id):
        self.survey_id = survey_id
        self.user_id = user_id

#### SMALL DATA MANAGEMENT CLASS ####
'''class DataMgr(object):

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

'''