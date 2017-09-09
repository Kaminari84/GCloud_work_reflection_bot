# -*- coding: utf-8 -*-
"""
Python DataMgr class for handling persistent data storage
"""
import logging
import os
import message
import operator
#import pickle
import datetime
import pytz
import random
from random import random, randrange

from datetime import datetime, timedelta
from pytz import timezone
from pytz import common_timezones
from pytz import country_timezones
from flask import Flask, request, make_response, render_template
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy
from sqlalchemy.engine import create_engine

logging.basicConfig(level=logging.INFO)


#### GLOBAL VARIABLES ####
team_bots = {}

UPLOAD_FOLDER = '/uploads'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Environment variables are defined in app.yaml.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URI']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_POOL_RECYCLE'] = 1

USER_RESPONSE_STYLE = os.environ['USER_RESPONSE_STYLE'] #TILL_DONE $ONE_ANSWER
RMD_DELAY = os.environ['RMD_DELAY']
MAX_RMDS = os.environ['MAX_RMDS']
SERVER_URL = os.environ['SERVER_URL']

db = SQLAlchemy(app)
#db = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], pool_recycle=1)


##########################
#### HELPER FUNCTIONS ####
##########################

def utcnow():
	return datetime.now(tz=pytz.utc)

def pstnow():
	utc_time = utcnow()
	pacific = timezone('US/Pacific')
	pst_time = utc_time.astimezone(pacific)
	return pst_time

def generate_pacific_date(year, month, day, hour, minute, second):
	pacific = timezone('US/Pacific')
	dt = datetime(year, month, day, hour, minute, second)
	in_pacific = pacific.localize(dt, is_dst=True)
	return in_pacific

def get_bot_for_participant(participant_id):
	user_details = Participant.query.filter_by(id=participant_id).first()
	logging.info("Got user details, id: "+user_details.id+", team_id: "+user_details.team_id+", slack_id: "+user_details.slack_id+", name: "+user_details.name)

	logging.info("Getting the team bot that handles this user")
	if user_details.team_id is not None:
		logging.info("There is team_id provided: " + user_details.team_id)
		if user_details.team_id in team_bots:
			logging.info("There is a bot that handles this team!")
			return team_bots[user_details.team_id]

	return None


##########################
#### DATABASE CLASSES ####
##########################

class TeamApproval(db.Model):
	id = db.Column(db.String(80), primary_key=True)
	authorization_token = db.Column(db.String(128))
	timestamp = db.Column(db.DateTime())

	def __init__(self, team_id, authorization_token):
		self.id = team_id
		self.timestamp = pstnow()
		self.authorization_token = authorization_token

class SurveyQuestionLog(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	timestamp = db.Column(db.DateTime())
	user_id = db.Column(db.String(80))
	survey_log_id = db.Column(db.Integer) 
	survey_id = db.Column(db.Integer)
	schedule_id = db.Column(db.Integer)
	question_id = db.Column(db.Integer)
	question_type = db.Column(db.String(80))
	text = db.Column(db.Text)

	def __init__(self, user_id, survey_log_id, survey_id, schedule_id, question_id, question_type, text):
		self.timestamp = pstnow()
		self.user_id = user_id
		self.survey_log_id = survey_log_id
		self.survey_id = survey_id
		self.schedule_id = schedule_id
		self.question_id = question_id
		self.question_type = question_type
		self.text = text

class AudioRecordingLog(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.String(80))
	timestamp = db.Column(db.DateTime())
	rqa_id = db.Column(db.Integer)
	rq_id = db.Column(db.Integer)
	rq_date = db.Column(db.DateTime())
	rq_type = db.column(db.String(50))
	audio_url = db.Column(db.String(512))

	def __init__(self, user_id, timestamp, rqa_id, rq_id, rq_date, rq_type, audio_url):
		self.user_id = user_id
		self.timestamp = timestamp
		self.rqa_id = rqa_id
		self.rq_id = rq_id
		self.rq_date = rq_date
		self.rq_type = rq_type
		self.audio_url = audio_url

class SurveyQuestion(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
	text = db.Column(db.String(256))

	def __init__(self, id, survey_id, text):
		self.id = id
		self.survey_id = survey_id
		self.text = text

# KEEPS THE ALL THE REFLECTIVE QUESTIONS WITHOUT USER ASSIGNMENT #
class ReflectiveQuestion(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	survey_id = db.Column(db.Integer)
	text = db.Column(db.String(256))
	type = db.Column(db.String(60))

	def __init__(self, id, survey_id, text, type):
		self.id = id
		self.survey_id = survey_id
		self.text = text
		self.type = type

class ReflectiveQuestionAssignment(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	question_id = db.Column(db.Integer)
	user_id = db.Column(db.String(80))
	date = db.Column(db.DateTime())
	task = db.Column(db.String(256))
	n_completed = db.Column(db.Integer)
	n_progress = db.Column(db.Integer)
	n_planned = db.Column(db.Integer)

	def __init__(self, user_id, question_id, date):
		self.user_id = user_id
		self.question_id = question_id
		self.date = date
		self.task = None
		self.n_completed = None
		self.n_progress = None
		self.n_planned = None

class SurveyLog(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.String(80))
	survey_id = db.Column(db.Integer)
	schedule_id = db.Column(db.Integer)
	time_started = db.Column(db.DateTime())
	time_completed = db.Column(db.DateTime())
	time_closed = db.Column(db.DateTime())

	def __init__(self, user_id, survey_id, schedule_id):
		self.user_id = user_id
		self.survey_id = survey_id
		self.schedule_id = schedule_id
		self.time_started = pstnow()
		self.time_completed = None
		self.time_closed = None

class SurveyReminderLog(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	user_id = db.Column(db.String(80))
	survey_log_id = db.Column(db.Integer)
	question_id = db.Column(db.Integer)
	timestamp = db.Column(db.DateTime())
	text = db.Column(db.String(120))

	def __init__(self, user_id, survey_log_id, question_id, text):
		self.user_id = user_id
		self.survey_log_id = survey_log_id
		self.question_id = question_id
		self.timestamp = pstnow()
		self.text = text

	@staticmethod
	def get_reminder_text(report_type, report_modality):
		reminders = {}
		reminders['REPORT_SLACK'] = [
					"You still have not answered the last question.", #: \"<question>\".",
					"Would you have some time to answer the last question?", # : \"<question>\"?",
					"Could you please answer the last question?", #: \"<question>\"?",
					"Would be great if you could answer the last question." #: \"<question>\"."
					]

		reminders['REFLECTION_WAND'] = [
					"Hey <name>, please remember to use the Alexa Dash to reflect.", #: \"<question>\".",
					"Hey <name>, could you please use your Alexa Dash to reflect?",
					"Hey <name>, would be great if you could find some time to reflect using your Amazon Dash.",
					"Hey <name>, please try to find some time to reflect using your Amazon Dash."
					]

		reminders['REFLECTION_SLACK'] = [
					"Hey <name>, please remember to reflect on your last question.", #: \"<question>\".",
					"Hey <name>, could you please reflect on the last question?",
					"Hey <name>, would be great if you could find some time to reflect based on the last question.",
					"Hey <name>, please try to find some time to reflect on the last question."
					]

		r_type = "REPORT_SLACK"
		rmd_id = report_type+"_"+report_modality
		logging.info("Constructed reminder ID: "+rmd_id)
		if rmd_id in reminders:
			r_type = rmd_id

		sel_id = randrange(0,len(reminders[r_type]))
		return reminders[r_type][sel_id]

class Survey(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(128))
	type = db.Column(db.String(60))
	modality = db.Column(db.String(32))
	start_text = db.Column(db.String(128))
	end_text = db.Column(db.String(128))
	questions = db.relationship('SurveyQuestion', backref='survey', lazy=True)

	def __init__(self, id, name, type, modality, start_text, end_text):
		self.id = id
		self.name = name
		self.type = type
		self.modality = modality
		self.start_text = start_text
		self.end_text = end_text

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

class Participant(db.Model):
	id = db.Column(db.String(80), primary_key=True)
	team_id = db.Column(db.String(80))
	slack_id = db.Column(db.String(80))
	name = db.Column(db.String(80))
	timezone = db.Column(db.String(80))
	email = db.Column(db.String(80))
	phone = db.Column(db.String(80))
	device_id = db.Column(db.String(256))
	time_added = db.Column(db.DateTime())
	state = db.Column(db.String(50))
	last_update = db.Column(db.DateTime())

	def __init__(self, team_id, slack_id, name, timezone = None, email = None, phone = None, device_id = None):
		self.id = team_id+"_"+slack_id
		self.team_id = team_id
		self.slack_id = slack_id
		self.name = name
		self.timezone = timezone
		self.email = email
		self.phone = phone
		self.device_id = device_id
		self.time_added = pstnow()
		self.state = "DAY_START"
		self.last_update = pstnow()

	def set_timezone(self, timezone):
		self.timezone = timezone

	def set_email(self, email):
		self.email = email

	def set_phone(self, phone):
		self.phone = phone

	def set_device_id(self, device_id):
		self.device_id = device_id

	def set_name(self, name):
		self.name = name

	def set_last_update(self, last_update):
		self.last_update = last_update

	def get_bot_reference(self):
		return get_bot_for_participant(self.id)

	def send_dm_message(self, text):
		bot_reference = self.get_bot_reference()

		if bot_reference:
			logging.info("Bot reference for user is OK")
			dm_channel = bot_reference.open_dm(self.slack_id)
			bot_reference.post_message(dm_channel, text)

			return True
		else:
			logging.warning("Bot reference missing for user id: "+self.id+", name: "+self.name)
			return False

	def get_reflective_question_for_now(self):
		logging.info("Trying to find the right reflective question for the current time and user state...")
		pst_now = pstnow()
		date_portion = generate_pacific_date(pst_now.year, pst_now.month, pst_now.day, 0, 0, 0)
		logging.info("Date for finding the reflective question for today: "+date_portion.isoformat(' '))

		#check whether we ask today's question or yesterday's question
		logging.info("Check whether to ask today's or yesterday's reflective question...")
		asked_today_already = SurveyLog.query.filter_by(user_id=self.id).filter(SurveyLog.time_started>date_portion).limit(10)
		work_reports_count = 0
		for report_log in asked_today_already:
			survey = Survey.query.get(report_log.survey_id)
			if survey:
				if survey.type == "REPORT":
					work_reports_count = work_reports_count + 1

		logging.info("Already asked work reports today check returned "+str(work_reports_count)+" entries!")
		
		reflective_question_data = self.construct_reflective_question_for_date(date_portion)
		if work_reports_count == 0:
			logging.info("No work reports answered today yet, will ask reflective question from yesterday then")
			question_date = date_portion - timedelta(days=1)
			reflective_question_data = self.construct_reflective_question_for_date(question_date)
		else:
			logging.info("Some work reports asked today, assume reflection question we generated for today is valid")

		if reflective_question_data and reflective_question_data['question_text']:
			logging.info("The reflective question have been found, question_text: " + reflective_question_data["question_text"])

		return {"question_text": reflective_question_data["question_text"],
				"question_assignment_id": reflective_question_data["question_assignment_id"],
				"question_id": reflective_question_data["question_id"],
				"question_date": reflective_question_data["question_date"]}

	def construct_reflective_question_for_date(self, qdate):
		logging.info("Constructing the reflective question for user id: "+self.id+", for date: "+qdate.isoformat(' '))

		question_text = None
		question_assignment_id = None
		question_id = None
		task = "the latest task"
		completed = 3
		progress = 1
		planned = 2 

		rqa = ReflectiveQuestionAssignment.query.filter_by(user_id=self.id, date=qdate).first()
		if rqa:
			logging.info("Found the reflective question assignment for today, id: "+str(rqa.id)+", question_id: "+str(rqa.question_id)+", user_id: "+str(rqa.user_id))
			rq = ReflectiveQuestion.query.get(rqa.question_id)
			if rq:
				logging.info("Found the corresponding reflective question, text: "+rq.text)
				if rqa.task != None:
					task = '"'+rqa.task+'"'
				
				if rqa.n_completed != None:
					completed = rqa.n_completed
				
				if rqa.n_progress != None:
					progress = rqa.n_progress
				
				if rqa.n_planned != None:
					planned = rqa.n_planned
				
				#replace the task
				question_text = rq.text.replace("<task>", task)
				question_text = question_text.replace("<completed>", '"'+str(completed)+'"')
				question_text = question_text.replace("<progress>", '"'+str(progress)+'"')
				question_text = question_text.replace("<planned>", '"'+str(planned)+'"')

				question_assignment_id = rqa.id
				question_id = rq.id

		else:
			logging.warning("No reflective question assigned for the user id: "+str(self.id)+", name: "+self.name+" for this day: "+qdate.isoformat(' '))

		return {"question_assignment_id": question_assignment_id, 
				"question_id": question_id, 
				"question_text": question_text,
				"question_date": qdate}


	def send_survey(self, survey):
		logging.info("Trying to send survey to participant ("+str(self.id)+", name: "+self.name+"), survey id: "+str(survey.id)+", name: "+survey.name)
		#get the survey questions
		survey_question = SurveyQuestion.query.filter_by(survey_id=survey.id).order_by(sqlalchemy.asc(SurveyQuestion.id)).first()
		if survey_question:
			logging.info("First question is: "+survey_question.text)

			nextState = Participant.construct_survey_question_state(survey.id, 0, survey_question.id) #"SURVEY_QUESTION_ASKED#"+str(survey.id)+"$"+str(survey_question.id)
			status = {  "stateChanged": True,
				"prevState": "DAY_START",
				"nextState": nextState
			}

			self.update(status = status)

			#send_survey_question(survey.id, survey_question.id)
		else:
			logging.warning("Survey has no questions!")

	def send_survey_question(self, survey_log_id, survey_id, schedule_id, question_id):
		logging.info("Trying to send survey question to participant ("+str(self.id)+", name: "+self.name+"), survey id: "+str(survey_id)+", q_id:"+str(question_id))
		#get the survey questions
		survey = Survey.query.filter_by(id=survey_id).first()
		if survey: 
			logging.info("Found a survey: "+str(survey.id)+", name: "+survey.name+", modality: "+survey.modality+" !")

			survey_question = SurveyQuestion.query.filter_by(survey_id=survey_id, id=question_id).first()
			if survey_question:
				logging.info("First raw question is: "+survey_question.text)

				question_text = survey_question.text
				logging.info("Checking if time to replace yesterday witn Friday")
				weekday = pstnow().weekday()
				logging.info("Week_day: "+str(weekday)+", survey_id: "+str(survey.id))
				if weekday == 0 and survey.id == 1:
					logging.info("yes, replace...")
					question_text = question_text.replace("yesterday", "on Friday")
					logging.info("After replacement: "+question_text)
				if survey_question.text == "REFLECTIVE_QUESTION":
					pst_now = pstnow()
					date_portion = generate_pacific_date(pst_now.year, pst_now.month, pst_now.day, 0, 0, 0)
					logging.info("Date for finding the reflective question: "+date_portion.isoformat(' '))
					
					question_data = self.get_reflective_question_for_now()
					question_text = question_data['question_text']				

				#behave differently based on modality
				send_success = False
				if survey.modality == "SLACK" and question_text:
					if self.send_dm_message(question_text):
						send_success = True
					else:
						logging.warning("Trying to send survey and user has no bot_reference!!!")

				elif survey.modality == "WAND":
					logging.info("Waiting for user to use the wand, question text is: "+question_text)
					send_success = True
				else:
					logging.warning("Unknown modality for survey! modality: <"+survey.modality+">")

				# sending the question has been a success - log it now!
				if send_success:
					logging.info("Send question success - logging")
					#log that we sent the message
					surveyQuestionLog = SurveyQuestionLog(
											user_id=self.id,
											survey_log_id=survey_log_id,
											survey_id=survey_id,
											schedule_id=schedule_id,
											question_id=survey_question.id,
											question_type="SURVEY_QUESTION",
											text=question_text)

					logging.info("Logging survey question sent to DB...")
					db.session.add(surveyQuestionLog)
					db.session.commit()
				else:
					logging.warning("Send question a failure - can't really log")
			else:
				logging.warning("The survey id:"+survey_id+" question id:"+question_id+" does not exist when trying to send it!")
		else:
			logging.warning("Can't find survey for id: "+survey_id)

	def send_end_survey_message(self, survey_log_id, survey_id, schedule_id):
		#find the survey
		survey = Survey.query.filter_by(id=survey_id).first()
		if survey:
			logging.info("Found a survey: "+str(survey.id)+", name:"+survey.name+"!")
			message_text = survey.end_text.replace("<name>", self.name)

			if survey.modality == "SLACK":
				if survey.type == "REPORT":
					message_text += "\n You can always check your dashboard: "+SERVER_URL+"/visualization?user_id="+self.id
				if not self.send_dm_message(message_text):
					logging.warning("Trying to send end survey message for survey_id:"+str(survey_id)+" and user has no bot_reference!!!")
			
			#log that we sent the message
			surveyQuestionLog = SurveyQuestionLog(
									user_id=self.id,
									survey_log_id=survey_log_id,
									survey_id=survey_id,
									schedule_id=schedule_id,
									question_id=None,
									question_type="SURVEY_COMPLETED",
									text=message_text)

			logging.info("Logging survey question sent to DB...")
			db.session.add(surveyQuestionLog)
			db.session.commit()
			
		else:
			logging.warning("Can't find survey for id: "+survey_id)

	def send_start_survey_message(self, survey_log_id, survey_id, schedule_id):		
		#find the survey
		survey = Survey.query.filter_by(id=survey_id).first()
		if survey:
			logging.info("Found a survey: "+str(survey.id)+", name:"+survey.name+"!")
			logging.info("User response style: "+USER_RESPONSE_STYLE)
			message_text = survey.start_text.replace("<name>", self.name)
			
			#check the modality of the survey
			logging.info("Survey modality: "+survey.modality)
			if survey.modality == "SLACK":
				if USER_RESPONSE_STYLE == "TILL_DONE":
					message_text += " Enter DONE in a separate line to complete answering a question." 

			if self.send_dm_message(message_text):
				#log that we sent the message
				surveyQuestionLog = SurveyQuestionLog(
										user_id=self.id,
										survey_log_id=survey_log_id,
										survey_id=survey_id,
										schedule_id=schedule_id,
										question_id=None,
										question_type="SURVEY_STARTED",
										text=message_text)

				logging.info("Logging survey question sent to DB...")
				db.session.add(surveyQuestionLog)
				db.session.commit()
			else:
				logging.warning("Trying to send survey and user has no bot_reference!!!")
		else:
			logging.warning("Can't find survey for id: "+survey_id)
	

	def handle_message(self, channel, text):
		logging.info("Handling message from user: "+text)

		logging.info("Getting the user state to log the survey: "+ self.state)

		survey_log_id = None
		survey_id = None
		schedule_id = None
		question_id = None

		if self.state.startswith("SURVEY_QUESTION_ASKED"):
			ids = Participant.extract_ids_from_survey_question_state(self.state)
			if "survey_id" in ids and "question_id" in ids and "schedule_id" in ids:
				survey_id = ids['survey_id']
				question_id = ids['question_id']
				schedule_id = ids['schedule_id']

				sls = SurveyLog.query.filter_by(user_id=self.id, survey_id=survey_id, schedule_id=schedule_id, time_closed=None).limit(10)
				if sls.count() > 1:
					logging.warning("We have have a problem, "+str(sls.count()) +" surveys were open at handle message!")
				if sls.count() > 0:
					survey_log_id = sls.first().id

		#log that we sent the message
		logging.info("Adding entry to the log, survey_log_id: "+str(survey_log_id))
		surveyQuestionLog = SurveyQuestionLog(
								user_id=self.id,
								survey_log_id=survey_log_id,
								survey_id=survey_id,
								schedule_id=schedule_id,
								question_id=question_id,
								question_type="USER_MESSAGE",
								text=text)

		logging.info("Logging survey question sent to DB...")
		db.session.add(surveyQuestionLog)
		db.session.commit()    

	def should_send_reminder(self, survey_id, question_id, schedule_id, survey_log_id):
		logging.info("In function to check if we should send reminder...")
		#get the number of reminders we have sent so far for this survey_log_id and this question_id
		n_reminders = 0
		if survey_log_id:
			rmd_list = SurveyReminderLog.query.filter_by(user_id=self.id, survey_log_id=survey_log_id, question_id=question_id).limit(30)
			n_reminders = rmd_list.count()
		else:
			logging.warning("We can't get schedule log id, no way to know how many reminders sent, returning False")
			return False

		#don't send more than 3 reminders per survey question in any case
		logging.info("Number of reminders sent so far: "+str(n_reminders ))
		if n_reminders >= int(MAX_RMDS):
			logging.info("Too many reminders sent already, returning False")
			return False

		#get last actvity time (including things sent by the system)
		sql = SurveyQuestionLog.query.filter_by(user_id=self.id).order_by(sqlalchemy.desc(SurveyQuestionLog.timestamp)).first()
		if sql:
			pst_now = pstnow()
			last_user_date = generate_pacific_date(sql.timestamp.year, sql.timestamp.month, sql.timestamp.day, sql.timestamp.hour, sql.timestamp.minute, sql.timestamp.second)
			#qtime = generate_pacific_date(pst_now.year, pst_now.month, pst_now.day, 0, 0, 0)
			logging.info("Current date: "+pst_now.isoformat(' ')+", last user interaction date: " + last_user_date.isoformat(' '))
			next_rmd_date = last_user_date+timedelta(minutes=int(RMD_DELAY))
			logging.info("Next reminder time: "+next_rmd_date.isoformat(' '))
			if (pst_now > next_rmd_date):
				logging.info("OK, time to send reminder now!")
				return True
			else:
				logging.info("Not yet time for a reminder!")
				return False

	def send_reminder(self, survey_id, question_id, schedule_id, survey_log_id):
		logging.info("Sending a reminder to user id: "+self.id+", name: "+self.name)
		survey = Survey.query.get(survey_id)
		survey_type = "REPORT"
		if survey:
			survey_type = survey.type

		rmd_text = SurveyReminderLog.get_reminder_text(survey.type, survey.modality)
		
		logging.info("Got reminder raw text: "+rmd_text+", replacing slots...")

		sq = SurveyQuestion.query.get(question_id)
		if sq:
			rmd_text = rmd_text.replace("<name>", self.name)
			rmd_text = rmd_text.replace("<question>", sq.text)
		else:
			logging.warn("Can't extract the text of the question, like the question with id: "+str(question_id)+" does not exist in DB anymore!")
			return False

		#send it
		logging.info("Attempting to send a reminder: "+rmd_text)
		if self.send_dm_message(rmd_text):
			logging.info("Success!!")

			#Log the reminder in the remindersinder table
			sqr = SurveyReminderLog(user_id = self.id,
									survey_log_id = survey_log_id,
									question_id = question_id,
									text = rmd_text)

			db.session.add(sqr)

			#log the reminder in the SurveyQuestionLog table
			sql = SurveyQuestionLog(
									user_id=self.id,
									survey_log_id=survey_log_id,
									survey_id=survey_id,
									schedule_id=schedule_id,
									question_id=question_id,
									question_type="SURVEY_QUESTION_REMINDER",
									text=rmd_text)

			logging.info("Logging survey question sent to DB...")
			db.session.add(sql)
			db.session.commit()
		else:
			logging.warning("Failed to send a reminder!")
			return False

	def update(self, status = None):
		logging.info("---------------------USER UPDATE-----------------------")
		logging.info("Updating user: "+self.id+", current state: "+self.state)

		logging.info("Checking state transition...")
		if not status:
			status = {  "stateChanged": False,
					"prevState": self.state,
					"nextState": self.state
					}

			status = Participant.transition_state(self.state, self.id)
		else:
			logging.info("Received the status as argument!")
	
		# IF STATE CHANGED
		if status['stateChanged']:
			logging.info("State change request from "+status['prevState']+" to "+status['nextState'])
			self.state = status['nextState']

			logging.info("Executing exit "+status['prevState']+" state function")
			Participant.exit_state(status['prevState'], self.id, status['nextState'])
			
			logging.info("Executing enter "+status['nextState']+" state function")
			Participant.enter_state(status['nextState'], self.id)
		else:
			logging.info("State has not changed!")
			logging.info("Executing in state "+status['prevState']+" function")
			Participant.in_state(status['prevState'], self.id)

		logging.info("Update complete for participant: "+self.id+", current state: "+self.state)
		self.set_last_update(pstnow())

	@staticmethod
	def transition_state(state, user_id):
		now = pstnow()
		logging.info("The time now is: "+now.isoformat(' '))

		#end_day_time = generate_pacific_date(int(now.year), int(now.month), int(now.day), 23, 30, 0)
		#logging.info("End day time is: "+end_day_time.isoformat(' '))

		status = {  "stateChanged": False,
					"prevState": state,
					"nextState": state 
				}

		today_week_day = now.weekday()
		hour_now = now.hour
		minute_now = now.minute
		today_minute_count = hour_now*60+minute_now

		logging.info("Week day: "+str(today_week_day)+", hour: "+str(hour_now)+", minute: "+str(minute_now)+", minute_count:"+str(today_minute_count))

		if state == "DAY_START":
			logging.info("The day has just started")
			#get the assigned survey time
			pas_assignments = ParticipantSurveyAssignment.query.filter_by(user_id=user_id).limit(10)
			if pas_assignments.count() == 0:
				logging.warning("No surveys assigned to the participant id: "+user_id)

			enabled_entries = {}
			for pas in pas_assignments:
				logging.info("There is survey assignment, get the survey id: "+str(pas.survey_id))
				survey = Survey.query.filter_by(id=pas.survey_id).first()
				if survey:
					logging.info("Found a survey: "+str(survey.id)+", name:"+survey.name+"!")
					logging.info("Checking it's schedule")
					survey_schedule = SurveySchedule.query.filter_by(survey_id=survey.id).limit(10)
					#just find the first time that matches

					#get the log of surveys asked today
					pst_now = pstnow()
					qtime = generate_pacific_date(pst_now.year, pst_now.month, pst_now.day, 0, 0, 0)
					logging.info("Questions today dates: " + qtime.isoformat(' '))

					#se = 1
					for schedule_entry in survey_schedule:
						schedule_minute_count = schedule_entry.hour*60+schedule_entry.minute
						logging.info("Schedule entry ["+str(schedule_entry.id)+"] -> week_day: "+str(schedule_entry.week_day)+", hour: "+str(schedule_entry.hour)+", minute:"+str(schedule_entry.minute)+", minute_count:"+str(schedule_minute_count))
						if schedule_entry.week_day == today_week_day:
							if today_minute_count > schedule_minute_count:
								#if report - check if asked today already
								asked_today_already = SurveyLog.query.filter_by(user_id=user_id, schedule_id=schedule_entry.id).filter(SurveyLog.time_started>qtime)
								if survey.type == "REPORT":
									logging.info("A work report is enabled, checking if asked already today!")
								if survey.type == "REFLECTION":
									logging.info("A reflection report is enabled, checking if we are before or after work report survey for today!")
									#important, check if any work report is filled today, not his pertciular schedule id one
									asked_today_already = SurveyLog.query.filter_by(user_id=user_id).filter(SurveyLog.time_started>qtime).limit(10)
									work_report_logs_today = []
									for report_log in asked_today_already:
										wrk_survey = Survey.query.get(report_log.survey_id)
										if wrk_survey:
											if wrk_survey.type == "REPORT":
												work_report_logs_today.append(report_log.id)
									
									logging.info("Work report count today: "+str(len(work_report_logs_today)))
									if len(work_report_logs_today) == 0:
										logging.info("We have not asked any work report yet today!")
										logging.info("Check if we have answered the reflective report today")
									else:
										logging.info("We have already answered a work report today!")
										logging.info("Extractig the time started of the latest work report")

										latest_work_report_start_date = SurveyLog.query.get(work_report_logs_today[0]).time_started
										logging.info("So presetting the latest start data to: "+latest_work_report_start_date.isoformat(' '))
										logging.info("Looping though other work reports today to see if there is something later...")
										for log_id in work_report_logs_today:
											logging.info("Found log entry to check: "+str(log_id))
											log_time = SurveyLog.query.get(log_id).time_started
											if log_time > latest_work_report_start_date:
												logging.info("Time started for this is actually later: "+log_time.isoformat(' '))
												latest_work_report_start_date = log_time

										logging.info("The final start time we have for the latest work report: "+latest_work_report_start_date.isoformat(' '))
										logging.info("Check if we have answered a reflective question after that")
										asked_today_already = SurveyLog.query.filter_by(user_id=user_id, schedule_id=schedule_entry.id).filter(SurveyLog.time_started>latest_work_report_start_date)
								




								#if reflection 
								#check if any work activity report filled today (type="REPORT")
								#if is activity report filled
									#check if there is this survey after the report last report fill completed date
									#if isn't 
										#then ask 

								#-------------------------------
										#check if this filled from the day before
										#if is 
											#then not enabled
										#if isn't from the day before
											#then ask from the day before (put planned_date day before) 
									#if is
										#not enabled
								#if isn't activity report filled yet
									#not enabled
									#check if the day before reflection is filled
									#if is
										#not enabled
									#if isn't
										#then ask from day before (put planned_date day before)
								#-------------------------------

								logging.info("Already asked today check returned "+str(asked_today_already.count())+" entries!")
								# only ask if not asked today yet
								if asked_today_already.count() == 0:
									logging.info("This schedule works for now and not asked yet today!")
									enabled_entries[schedule_entry.id] = (schedule_minute_count, survey.id, schedule_entry.id)
								else:
									logging.info("Can't ask, already asked today, schedule id: "+str(schedule_entry.id))

						#se = se+1
				else:
					logging.warning("No survey object for survey assignment! survey_ass_id: "+str(pas.id)+", survey id:"+str(pas.survey_id))

			sel_survey_id = 0
			sel_schedule_id = 0
			logging.info("We have "+str(len(enabled_entries))+" surveys that can be asked now, selecting earliest!")
			if len(enabled_entries) > 0:
				for key, value in enabled_entries.items():
					logging.info("Key: "+str(key) +", Value: "+str(value))
				
				sorted_entries = sorted(enabled_entries.items(), key=operator.itemgetter(1))
				logging.info("Sorted entries:")
				for entry in sorted_entries:
					logging.info("Entry: "+str(entry))

				sel_survey_id = sorted_entries[0][1][1]
				sel_schedule_id = sorted_entries[0][1][2]

			logging.info("Selected survey id: "+str(sel_survey_id)+", selected schedule id: "+str(sel_schedule_id))

			if sel_survey_id > 0 and sel_schedule_id > 0:
				logging.info("OK, seems we are running the survey!")

				sq = SurveyQuestion.query.filter_by(survey_id=sel_survey_id).order_by(sqlalchemy.asc(SurveyQuestion.id)).first()
				if sq:
					logging.info("First question id: "+str(sq.id)+" is: "+sq.text)
				
					nextState = Participant.construct_survey_question_state(sel_survey_id, sel_schedule_id, sq.id) #"SURVEY_QUESTION_ASKED#"+str(survey.id)+"$"+str(sq.id)
					logging.info("Changing state to "+nextState)
					status['stateChanged'] = True
					status['nextState'] = nextState
				else:
					logging.warning("Empty survey? survey_id:"+sel_survey_id)
			
			logging.info("Done update in state: "+state)
			#if now > end_day_time:
			#	logging.info("Changing state to END_DAY")
			#	status['stateChanged'] = True
			#	status['nextState'] = "END_DAY"
			#else:
			#	logging.info("Waiting for end of day")

		elif state.startswith("SURVEY_QUESTION_ASKED"):
			logging.info("We are in survey question asking state")
			#determine survey id and question id
			ids = Participant.extract_ids_from_survey_question_state(state)
			if "survey_id" in ids and "question_id" in ids and "schedule_id" in ids:
				survey_id = ids['survey_id']
				question_id = ids['question_id']
				schedule_id = ids['schedule_id']

				logging.info("Determine if the question has been answered")
				#Get when the survey id, question id has been asked the last time for this user
				sql_question = SurveyQuestionLog.query.filter_by(user_id=user_id, survey_id=survey_id, schedule_id=schedule_id, question_id=question_id, question_type="SURVEY_QUESTION").order_by(sqlalchemy.desc(SurveyQuestionLog.timestamp)).first()
				if sql_question:
					logging.info("Found the matching question asked at: "+sql_question.timestamp.isoformat(' ')+", probably should check if the same day, but we are not doing it now")
					logging.info("Now get all the answers from this user afterwards...")

					qtime = generate_pacific_date(sql_question.timestamp.year, sql_question.timestamp.month, sql_question.timestamp.day, sql_question.timestamp.hour, sql_question.timestamp.minute, sql_question.timestamp.second)
					logging.info("Cut off date from question: " + qtime.isoformat(' '))

					logging.info("Check modality of how the question was asked...")
					
					modality = "SLACK"
					survey = Survey.query.get(survey_id)
					if survey:
						logging.info("Survey found, getting modality...")
						modality = survey.modality
						logging.info("Modality is: "+modality)
					else:
						logging.warning("Survey not found, using default modality: "+modality)

					ans_type = "USER_MESSAGE"
					if modality=="WAND":
						ans_type = "USER_VOICE_MESSAGE"

					sql_answers = SurveyQuestionLog.query.filter(SurveyQuestionLog.timestamp>qtime).filter_by(user_id=user_id, question_type=ans_type).order_by(sqlalchemy.desc(SurveyQuestionLog.timestamp)).limit(20)
					#
					#sql_answers = SurveyQuestionLog.query.filter_by(user_id=user_id, question_type=ans_type).order_by(sqlalchemy.desc(SurveyQuestionLog.timestamp)).limit(20)
					
					if sql_answers:
						logging.info("Got "+str(sql_answers.count())+" answers...")
						n = 1
						for ans in sql_answers:
							logging.info("Got answer ["+str(n)+"]: "+ans.text)
							n=n+1

						if Participant.is_answering_finished(sql_answers, modality, USER_RESPONSE_STYLE): #TILL_DONE #ONE_ANSWER
							logging.info("Answering done, move to next question")
							
							survey_question = SurveyQuestion.query.filter_by(survey_id=survey_id).filter(SurveyQuestion.id>question_id).order_by(sqlalchemy.asc(SurveyQuestion.id)).first()
							if survey_question:
								nextState = Participant.construct_survey_question_state(survey_id, schedule_id, survey_question.id) #"SURVEY_QUESTION_ASKED#"+str(survey_question.survey_id)+"$"+str(survey_question.id)
								logging.info("Found next question, changing state to "+nextState)
								status['stateChanged'] = True
								status['nextState'] = nextState
							else:
								logging.info("This was the last question in this survey")
								nextState = Participant.construct_survey_completed_state(survey_id, schedule_id) #"SURVEY_COMPLETED#"+str(survey_id)
								status['stateChanged'] = True
								status['nextState'] = nextState
						else:
							logging.info("Not done yet, waiting for user to finish")
					else:
						logging.info("No answers yet, waiting still...")
				else:
					logging.warning("No question found in logs, seems like we did not asked it, what to do now?")
					logging.info("Waiting for end of day")

			#elif now > end_day_time:
			#	logging.info("Changing state to END_DAY")
			#	status['stateChanged'] = True
			#	status['nextState'] = "END_DAY"
			#else:
			#	logging.warning("Can't extract survey and question if from a survey state: "+state)
			#	logging.info("Waiting for the end of day")

			logging.info("Done update in state: "+state)

		elif state.startswith("SURVEY_COMPLETED"):
			logging.info("We just completed a survey!")
			
			sid = Participant.extract_ids_from_survey_state(state)
			if "survey_id" in sid and "schedule_id" in sid:
				survey_id = sid['survey_id']
				schedule_id = sid['schedule_id']

				logging.info("Full loop, going back to parking state after completing a survey...")
				status['stateChanged'] = True
				status['nextState'] = "DAY_START"

			#elif now > end_day_time:
			#	logging.info("Changing state to END_DAY")
			#	status['stateChanged'] = True
			#	status['nextState'] = "END_DAY"
			#else:
			#	logging.warning("Can't extract survey and question id from a survey completed state: "+state)
			#	logging.info("Waiting for the end of day")

			logging.info("Done update in state: "+state)
			
		else:
			logging.warning("Unknown state: "+state)

		return status

	@staticmethod
	def enter_state(state, user_id):
		logging.info("In enter state, state: "+state+", user_id: "+user_id)

		#ok, time to send the question if we are in this state
		if state.startswith("SURVEY_QUESTION_ASKED"):
			ids = Participant.extract_ids_from_survey_question_state(state)
			if "survey_id" in ids and "question_id" in ids and "schedule_id" in ids:
				survey_id = ids['survey_id']
				schedule_id = ids['schedule_id']
				question_id = ids['question_id']

				logging.info("Sending survey id: "+str(survey_id)+", schedule id: "+str(schedule_id)+", question id: "+str(question_id)+" to user id: "+user_id)
				user = Participant.query.filter_by(id=user_id).first()
				if user:
					#log that the survey has been completed
					survey_log_id = None
					sls = SurveyLog.query.filter_by(user_id=user_id, survey_id=survey_id, schedule_id=schedule_id, time_closed=None).limit(10)
					if sls.count() > 1:
						logging.warning("We have have a problem, "+str(sls.count()) +" surveys were open at survey question asked enter state")
					if sls.count() > 0:
						survey_log_id = sls.first().id

					logging.info("User found, name: "+user.name)
					user.send_survey_question(survey_log_id, survey_id, schedule_id, question_id)
				else:
					logging.warning("Can't find user to send the question to in enter_state")
			else:
				logging.warning("Can't extract survey and question if from a survey state: "+state+" in enter state")
		elif state.startswith("SURVEY_COMPLETED"):
			sid = Participant.extract_ids_from_survey_state(state)
			if "survey_id" in sid and "schedule_id" in sid:
				survey_id = sid['survey_id']
				schedule_id = sid['schedule_id']

				logging.info("Sending survey completed thanks, survey id:"+survey_id)
				user = Participant.query.filter_by(id=user_id).first()
				if user:
					logging.info("User found, name: "+user.name)
					

					#log that the survey has been completed
					survey_log_id = None
					sls = SurveyLog.query.filter_by(user_id=user_id, survey_id=survey_id, schedule_id=schedule_id, time_closed=None).limit(10)
					if sls.count() > 1:
						logging.warning("We have have a problem, "+str(sls.count()) +" surveys were open at closing state, closing them all, but it should not have happened!")
					if sls.count() > 0:
						survey_log_id = sls.first().id

					user.send_end_survey_message(survey_log_id, survey_id, schedule_id)

					for sl in sls:
						logging.info("Completing and closing the survey log: "+str(sl.id)+", survey_id:"+str(sl.survey_id)+" for user: "+sl.user_id+", opened on: "+sl.time_started.isoformat(' '))
						sl.time_completed = pstnow()
						sl.time_closed = pstnow()

					db.session.commit()
				else:
					logging.warning("Can't find user to send the question to in enter_state")

		else:
			logging.info("Nothing to do in ENTER STARE for state: "+state)

	@staticmethod
	def in_state(state, user_id):
		if state == "DAY_START" or state.startswith("SURVEY_COMPLETED"):
			logging.info("I am in state: "+state)
			
			user = Participant.query.filter_by(id=user_id).first()
			if user:
				pass
				#user.send_dm_message("Hey, I am just a work reflection study bot and will send you a work report request soon. I can't do much more at the moment.")
			else:
				logging.warning("Can't find user to send the reply to in IN_STATE!")
		elif state.startswith("SURVEY_QUESTION_ASKED"):
			survey_id = None
			schedule_id = None
			question_id = None
			if state.startswith("SURVEY_QUESTION_ASKED"):
				ids = Participant.extract_ids_from_survey_question_state(state)
				if "survey_id" in ids and "question_id" in ids and "schedule_id" in ids:
					survey_id = ids['survey_id']
					schedule_id = ids['schedule_id']
					question_id = ids['question_id']
				else:
					logging.warning("We can't extract survey details, so no info about reminders sent, returning false, state: "+self.state)
					return False
			else:
				logging.warning("We are not in the survey question state and reminder check was asked, returning false, state: "+self.state)
				return False

			survey_log_id = None
			sls = SurveyLog.query.filter_by(user_id=user_id, survey_id=survey_id, schedule_id=schedule_id, time_closed=None).limit(10)
			if sls.count() > 1:
				logging.warning("We have have a problem, "+str(sls.count()) +" surveys were open at checking if to send reminder")
			if sls.count() > 0:
				survey_log_id = sls.first().id
				logging.info("Got survey_log_id: "+str(survey_log_id))
			else:
				logging.warning("No corresponding survey log in state: "+state)

			if survey_id and question_id and schedule_id and survey_log_id:
				user = Participant.query.filter_by(id=user_id).first()
				if user:
					if user.should_send_reminder(survey_id, question_id, schedule_id, survey_log_id):
						user.send_reminder(survey_id, question_id, schedule_id, survey_log_id)	
					else:
						logging.info("It is not a time for reminder just yet!")
				else:
					logging.warning("Can't find user to send the reminder to in IN_STATE!")
			else:
				logging.warning("Cant' extract all the needed state information in IN STATE@")
				
	@staticmethod
	def exit_state(state, user_id, next_state):
		logging.info("Exiting state: "+state)
		if state=="DAY_START" and next_state.startswith("SURVEY_QUESTION_ASKED"):
			logging.info("Exiting DAY_START to ask questionnaire")
			sid = Participant.extract_ids_from_survey_question_state(next_state)
			if "survey_id" in sid and "schedule_id" in sid:
				survey_id = sid['survey_id']
				schedule_id = sid['schedule_id']

				user = Participant.query.filter_by(id=user_id).first()
				if user:
					logging.info("User found, name: "+user.name)

					# Adding the entry to sruvey_log
					sl = SurveyLog(
						user_id=user_id,
						survey_id=survey_id,
						schedule_id=schedule_id
					)

					logging.info("Trying to add survey started log: "+str(survey_id)+", schedule id:"+schedule_id+" for user: "+str(user_id)+" to DB...")
					db.session.add(sl)
					db.session.flush()
					db.session.refresh(sl)

					user.send_start_survey_message(sl.id, survey_id, schedule_id)

					db.session.commit()
				else:
					logging.warning("Can't find user to send the welcome message to in enter_stare handling, state: "+state)
			else:
				logging.warning("Can't find survey we are switching to in enter_stare handling, next state:" + next_state)
		else:
			logging.info("Exiting "+state+" to do something else than ask questionnaire - next_state: " + next_state)

	@staticmethod
	def is_answering_finished(responses, modality, method):
		logging.info("Detrmining if answering the question is done")
		if modality == "SLACK":
			if method == "ONE_ANSWER":
				if responses.count() > 0:
					return True
				else:
					return False
			elif method == "TILL_DONE":
				for ans in responses:
					text = ans.text.replace(' ','')
					if "done".upper() == text.upper():
						return True
					else:
						return False
		elif modality == "WAND":
			if responses.count() > 0:
				return True
			else:
				return False
		
		return False

	@staticmethod
	def construct_survey_question_state(survey_id, schedule_id, question_id):
		logging.info("Constructing survey question state for survey id: "+str(survey_id) +", question id: "+str(question_id)+", schedule id: "+str(schedule_id))
		state_string = "SURVEY_QUESTION_ASKED#"+str(survey_id)+"$"+str(question_id)+"%"+str(schedule_id)
		logging.info("Constructed state string: "+state_string)

		return state_string

	@staticmethod
	def construct_survey_completed_state(survey_id, schedule_id):
		logging.info("Constructing survey completed state for survey id: "+str(survey_id) +", schedule id: "+str(schedule_id))
		state_string = "SURVEY_COMPLETED#"+str(survey_id)+"%"+str(schedule_id)
		logging.info("Constructed state string: "+state_string)

		return state_string

	@staticmethod
	def extract_ids_from_survey_question_state(state):
		logging.info("Trying to extract survey id and question id from state: "+state)
		s_idx = state.find("#")
		q_idx = state.find("$")
		t_idx = state.find("%")

		if s_idx > -1 and q_idx > -1 and t_idx > -1:
			s_id = state[s_idx+1:q_idx]
			q_id = state[q_idx+1:t_idx]
			t_id = state[t_idx+1:]

			logging.info("Survey id: "+s_id+", question id: "+q_id+", schedule_id: "+t_id)
			return {"survey_id": s_id, "question_id": q_id, "schedule_id": t_id}

		else:
			logging.warning("We are in trouble, we are in survey question state, but the survey id or question id are not passed!!!")

		return {}

	@staticmethod
	def extract_ids_from_survey_state(state):
		logging.info("Trying to extract survey id  from state: "+state)
		s_idx = state.find("#")
		t_idx = state.find("%")

		if s_idx > -1 and t_idx > -1:
			s_id = state[s_idx+1:t_idx]
			t_id = state[t_idx+1:]

			logging.info("Survey id: "+s_id+", Schedule id: "+t_id)
			return {"survey_id": s_id, "schedule_id": t_id}
		else:
			logging.warning("We are in trouble, we are in survey question state, but the survey id is not passed!!!")
		
		return {}


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