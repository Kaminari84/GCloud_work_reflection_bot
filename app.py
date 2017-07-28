# -*- coding: utf-8 -*-
"""
A routing layer for the onboarding bot tutorial built using
[Slack's Events API](https://api.slack.com/events-api) in Python
"""
import logging
import uuid
import datetime
import socket
import time
import json
import os
from flask import Flask, request, make_response, render_template
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy
#from dataMgr import DataMgr
import dataMgr
from dataMgr import app
from dataMgr import db
from dataMgr import TeamApproval
from dataMgr import SurveyQuestionLog
from dataMgr import SurveyQuestion
from dataMgr import Survey
from dataMgr import SurveySchedule
from dataMgr import ParticipantSurveyAssignment

from dataMgr import team_bots
from bot import Bot
from enum import Enum

logging.basicConfig(level=logging.INFO)

USER_RESPONSE_STYLE = os.environ['USER_RESPONSE_STYLE'] #TILL_DONE $ONE_ANSWER

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

    def __init__(self, team_id, slack_id, name, timezone = None, email = None, phone = None, device_id = None):
        self.id = team_id+"_"+slack_id
        self.team_id = team_id
        self.slack_id = slack_id
        self.name = name
        self.timezone = timezone
        self.email = email
        self.phone = phone
        self.device_id = device_id
        self.time_added = datetime.datetime.utcnow()
        self.state = "DAY_START"

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


    def send_survey(self, survey):
        logging.info("Trying to send survey to participant ("+str(self.id)+", name: "+self.name+"), survey id: "+str(survey.id)+", name: "+survey.name)
        #get the survey questions
        survey_question = SurveyQuestion.query.filter_by(survey_id=survey.id).order_by(sqlalchemy.asc(SurveyQuestion.id)).first()
        if survey_question:
            logging.info("First question is: "+survey_question.text)

            nextState = "SURVEY_QUESTION_ASKED#"+str(survey.id)+"$"+str(survey_question.id)
            status = {  "stateChanged": True,
                "prevState": "DAY_START",
                "nextState": nextState
            }

            self.update(status = status)

            #send_survey_question(survey.id, survey_question.id)
        else:
            logging.warning("Survey has no questions!")

    def send_survey_question(self, survey_id, question_id):
        logging.info("Trying to send survey question to participant ("+str(self.id)+", name: "+self.name+"), survey id: "+str(survey_id)+", q_id:"+str(question_id))
        #get the survey questions
        survey_question = SurveyQuestion.query.filter_by(survey_id=survey_id, id=question_id).first()
        if survey_question:
            logging.info("First question is: "+survey_question.text)

            if self.send_dm_message(survey_question.text):
                #log that we sent the message
                surveyQuestionLog = SurveyQuestionLog(
                                        user_id=self.id,
                                        survey_id=survey_id,
                                        question_id=survey_question.id,
                                        question_type="SURVEY",
                                        text=survey_question.text)

                logging.info("Logging survey question sent to DB...")
                db.session.add(surveyQuestionLog)
                db.session.commit()
            else:
                logging.warning("Trying to send survey and user has no bot_reference!!!")
        else:
            logging.warning("The survey id:"+survey_id+" question id:"+question_id+" does not exist when trying to send it!")

    def send_end_survey_message(self, survey_id):
        message_text = "Thanks for completing your activity report!"

        if self.send_dm_message(message_text):
            #log that we sent the message
            surveyQuestionLog = SurveyQuestionLog(
                                    user_id=self.id,
                                    survey_id=survey_id,
                                    question_id=None,
                                    question_type="SURVEY_COMPLETED",
                                    text=message_text)

            logging.info("Logging survey question sent to DB...")
            db.session.add(surveyQuestionLog)
            db.session.commit()
        else:
            logging.warning("Trying to send survey and user has no bot_reference!!!")

    def send_start_survey_message(self):
        message_text = "Hey, it is time for your activity report today!"

        if self.send_dm_message(message_text):
            #log that we sent the message
            surveyQuestionLog = SurveyQuestionLog(
                                    user_id=self.id,
                                    survey_id=None,
                                    question_id=None,
                                    question_type="SURVEY_STARTED",
                                    text=message_text)

            logging.info("Logging survey question sent to DB...")
            db.session.add(surveyQuestionLog)
            db.session.commit()
        else:
            logging.warning("Trying to send survey and user has no bot_reference!!!")
    

    def handle_message(self, channel, text):
        logging.info("Handling message from user: "+text)

        #logging.info("Gettinf the latest question that has been asked")

        #log that we sent the message
        surveyQuestionLog = SurveyQuestionLog(
                                user_id=self.id,
                                survey_id=None,
                                question_id=None,
                                question_type="USER_MESSAGE",
                                text=text)

        logging.info("Logging survey question sent to DB...")
        db.session.add(surveyQuestionLog)
        db.session.commit()

    def determine_user_state(self):
        logging.info("Determining user "+self.id+" state...")
        #SurveyQuestionLog.query.filter_by(user_id=self.id, timestamp).first())     

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
    
        if status['stateChanged']:
            logging.info("State change request from "+status['prevState']+" to "+status['nextState'])
            self.state = status['nextState']

            logging.info("Executing exit "+status['prevState']+" state function")
            Participant.exit_state(status['prevState'], self.id)
            
            logging.info("Executing enter "+status['nextState']+" state function")
            Participant.enter_state(status['nextState'], self.id)
        else:
            logging.info("State has not changed!")
            logging.info("Executing in state "+status['prevState']+" function")
            Participant.in_state(status['prevState'], self.id)

        logging.info("Update complete for participant: "+self.id+", current state: "+self.state)

    @staticmethod
    def transition_state(state, user_id):
        now = datetime.datetime.now()
        logging.info("The time now is: "+now.isoformat(' '))

        end_day_time = datetime.datetime(now.year, now.month, now.day, 23, 30)
        logging.info("End day time is: "+end_day_time.isoformat(' '))

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
            for pas in pas_assignments:
                logging.info("There is survey assignment, get the survey id: "+str(pas.survey_id))
                survey = Survey.query.filter_by(id=pas.survey_id).first()
                if survey:
                    logging.info("Found a survey: "+str(survey.id)+", name:"+survey.name+"!")
                    logging.info("Checking it's schedule")
                    survey_schedule = SurveySchedule.query.filter_by(survey_id=survey.id).limit(10)
                    #just find the first time that matches
                    se = 1
                    run_survey = False
                    for schedule_entry in survey_schedule:
                        schedule_minute_count = schedule_entry.hour*60+schedule_entry.minute
                        logging.info("Schedule entry ["+str(se)+"] -> week_day: "+str(schedule_entry.week_day)+", hour: "+str(schedule_entry.hour)+", minute:"+str(schedule_entry.minute)+", minute_count:"+str(schedule_minute_count))
                        if schedule_entry.week_day == today_week_day:
                            if today_minute_count > schedule_minute_count:
                                logging.info("This schedule works for now!")
                                run_survey = True

                    if run_survey:
                        logging.info("OK, seems we are running the survey!")
                        sq = SurveyQuestion.query.filter_by(survey_id=survey.id).order_by(sqlalchemy.asc(SurveyQuestion.id)).first()
                        if sq:
                            logging.info("First question id: "+str(sq.id)+" is: "+sq.text)
                            
                            nextState = "SURVEY_QUESTION_ASKED#"+str(survey.id)+"$"+str(sq.id)
                            logging.info("Changing state to "+nextState)
                            status['stateChanged'] = True
                            status['nextState'] = nextState
                            break
                        else:
                            logging.warning("Empty survey? survey_id:"+survey.id)
                else:
                    logging.warning("No survey object for survey assignment! survey_ass_id: "+str(pas.id)+", survey id:"+str(pas.survey_id))

            if now > end_day_time:
                logging.info("Changing state to END_DAY")
                status['stateChanged'] = True
                status['nextState'] = "END_DAY"
            else:
                logging.warning("No surveys assigned to the participant id: "+user_id)
                logging.info("Waiting for end of day")

        elif state.startswith("SURVEY_QUESTION_ASKED"):
            logging.info("We are in survey question asking state")
            #determine survey id and question id
            ids = Participant.extract_ids_from_survey_question_state(state)
            if "survey_id" in ids and "question_id" in ids:
                survey_id = ids['survey_id']
                question_id = ids['question_id']

                logging.info("Determine if the question has been answered")
                #Get when the survey id, question id has been asked the last time for this user
                sql_question = SurveyQuestionLog.query.filter_by(user_id=user_id, survey_id=survey_id, question_id=question_id).order_by(sqlalchemy.desc(SurveyQuestionLog.timestamp)).first()
                if sql_question:
                    logging.info("Found the matching questions asked at: "+sql_question.timestamp.isoformat(' ')+", probably should check if the same day, but we are not doing it now")
                    logging.info("Now get all the answers from this user afterwards...")

                    qtime = datetime.datetime(sql_question.timestamp.year, sql_question.timestamp.month, sql_question.timestamp.day, sql_question.timestamp.hour, sql_question.timestamp.minute, sql_question.timestamp.second)
                    logging.info("Cut off date from question: " + qtime.isoformat(' '))

                    sql_answers = SurveyQuestionLog.query.filter(SurveyQuestionLog.timestamp>qtime).filter_by(user_id=user_id, question_type="USER_MESSAGE").order_by(sqlalchemy.desc(SurveyQuestionLog.timestamp)).limit(20)
                    if sql_answers:
                        logging.info("Got "+str(sql_answers.count())+" answers...")
                        n = 1
                        for ans in sql_answers:
                            logging.info("Got answer ["+str(n)+"]: "+ans.text)
                            n=n+1

                        if Participant.is_answering_finished(sql_answers, USER_RESPONSE_STYLE): #TILL_DONE $ONE_ANSWER
                            logging.info("Answering done, move to next question")
                            
                            survey_question = SurveyQuestion.query.filter_by(survey_id=survey_id).filter(SurveyQuestion.id>question_id).order_by(sqlalchemy.asc(SurveyQuestion.id)).first()
                            if survey_question:
                                nextState = "SURVEY_QUESTION_ASKED#"+str(survey_question.survey_id)+"$"+str(survey_question.id)
                                logging.info("Found next question, changing state to "+nextState)
                                status['stateChanged'] = True
                                status['nextState'] = nextState
                            else:
                                logging.info("This was the last question in this survey")
                                nextState = "SURVEY_COMPLETED#"+str(survey_id)
                                status['stateChanged'] = True
                                status['nextState'] = nextState
                        else:
                            logging.info("Not done yet, waiting for user to finish")
                    else:
                        logging.info("No answers yet, waiting still...")
                else:
                    logging.warning("No question found in logs, seems like we did not asked it, what to do now?")
                    logging.info("Waiting for end of day")

            elif now > end_day_time:
                logging.info("Changing state to END_DAY")
                status['stateChanged'] = True
                status['nextState'] = "END_DAY"
            else:
                logging.warning("Can't extract survey and question if from a survey state: "+state)
                logging.info("Waiting for the end of day")

        elif state.startswith("SURVEY_COMPLETED"):
            logging.info("We just completed a survey!")



            if now > end_day_time:
                logging.info("Changing state to END_DAY")
                status['stateChanged'] = True
                status['nextState'] = "END_DAY"
            else:
                logging.warning("Can't extract survey and question if from a survey state: "+state)
                logging.info("Waiting for the end of day")
            
        else:
            logging.warning("Unknown state: "+state)

        return status

    @staticmethod
    def enter_state(state, user_id):
        logging.info("In enter state, state: "+state+", user_id: "+user_id)

        #ok, time to send the question if we are in this state
        if state.startswith("SURVEY_QUESTION_ASKED"):
            ids = Participant.extract_ids_from_survey_question_state(state)
            if "survey_id" in ids and "question_id" in ids:
                survey_id = ids['survey_id']
                question_id = ids['question_id']

                logging.info("Sending survey id: "+survey_id+", question id: "+question_id+" to user id: "+user_id)
                user = Participant.query.filter_by(id=user_id).first()
                if user:
                    logging.info("User found, name: "+user.name)
                    user.send_survey_question(survey_id, question_id)
                else:
                    logging.warning("Can't find user to send the question to in enter_state")
            else:
                logging.warning("Can't extract survey and question if from a survey state: "+state+" in enter state")
        elif state.startswith("SURVEY_COMPLETED"):
            sid = Participant.extract_ids_from_survey_state(state)
            if "survey_id" in sid:
                survey_id = sid['survey_id']

                logging.info("Sending survey completed thanks, survey id:"+survey_id)
                user = Participant.query.filter_by(id=user_id).first()
                if user:
                    logging.info("User found, name: "+user.name)
                    user.send_end_survey_message(survey_id)
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
        

    @staticmethod
    def exit_state(state, user_id):
        if state == "DAY_START":
            logging.info("Sending survey start welcome")
            user = Participant.query.filter_by(id=user_id).first()
            if user:
                logging.info("User found, name: "+user.name)
                user.send_start_survey_message()
            else:
                logging.warning("Can't find user to send the welcome message to in EXIT_STATE!")

    @staticmethod
    def is_answering_finished(responses, method):
        logging.info("Detrmining if answering the question is done")
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
        return False


    @staticmethod
    def extract_ids_from_survey_question_state(state):
        logging.info("Trying to extract survey id and question id from state: "+state)
        s_idx = state.find("#")
        q_idx = state.find("$")

        if s_idx > -1 and q_idx > -1:
            s_id = state[s_idx+1:q_idx]
            q_id = state[q_idx+1:]

            logging.info("Survey id: "+s_id+", question id: "+q_id)
            return {"survey_id": s_id, "question_id": q_id}

        else:
            logging.warning("We are in trouble, we are in survey question state, but the survey id or question id are not passed!!!")

        return {}

    @staticmethod
    def extract_ids_from_survey_state(state):
        logging.info("Trying to extract survey id  from state: "+state)
        s_idx = state.find("#")

        if s_idx > -1 :
            s_id = state[s_idx+1:]

            logging.info("Survey id: "+s_id)
            return {"survey_id": s_id}
        else:
            logging.warning("We are in trouble, we are in survey question state, but the survey id is not passed!!!")
        
        return {}


def _event_handler(event_type, slack_event):
    """
    A helper function that routes events from Slack to our Bot
    by event type and subtype.

    Parameters
    ----------
    event_type : str
        type of event recieved from Slack
    slack_event : dict
        JSON response from a Slack reaction event

    Returns
    ----------
    obj
        Response object with 200 - ok or 500 - No Event Handler error

    """
    team_id = slack_event["team_id"]
    logging.info("Handling event for team id: <"+team_id+">")
    
    if event_type == "message":
        logging.info("Got into the message handler!")
        channel = slack_event["event"]["channel"]
        logging.info("Channel is: "+str(channel))
        #user_id = slack_event["event"].get("user")
        #pyBot.post_message(team_id, channel)
        #get the correct team bot to handle the request
        if team_id in team_bots:
            #team_bots[team_id].handle_message(slack_event) #post_message(channel)

            channel = slack_event['event']['channel']
            message_text = ""
            if 'text' in slack_event['event']:
                message_text = slack_event['event']['text']
            if 'user' in slack_event['event']:
                creator_id = slack_event['event']['user']

                bot_id = team_bots[team_id].get_bot_id()
                at_bot = "<@" + bot_id + ">"

                should_add = False
                if channel.startswith("D") and creator_id != bot_id and at_bot not in message_text:
                    should_add = True
                elif channel.startswith("D") and creator_id != bot_id and at_bot in message_text:
                    should_add = True
                elif channel.startswith("C") and creator_id != bot_id and at_bot in message_text:
                    should_add = True
                elif channel.startswith("C") and creator_id != bot_id and at_bot not in message_text:
                    should_add = False

                if should_add:
                    #log messages to DB here for now
                    logging.info("Got message, now find the user object that should handle it")
                    participant = Participant.query.filter_by(team_id=team_id, slack_id=creator_id).first()
                    if participant:
                        logging.info("Participant object found to handle the message")
                        participant.handle_message(channel, message_text)
                        participant.update()
                    else:
                        logging.warning("No participant found that can handle this message!")
                        team_bots[team_id].post_message(channel, "Hey I am just a work reflection study bot and you are not a participant. Would you like to join?")

        else:
            logging.warning("No bot found for the team id: <"+team_id+">")
        return make_response("I am responding to your message!", 200, )

    # ============= Event Type Not Found! ============= #
    # If the event_type does not have a handler
    message = "You have not added an event handler for the %s" % event_type
    # Return a helpful error message
    return make_response(message, 200, {"X-Slack-No-Retry": 1})

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

@app.route("/install", methods=["GET"])
def pre_install():
    """This route renders the installation page with 'Add to Slack' button."""
    # Since we've set the client ID and scope on our Bot object, we can change
    # them more easily while we're developing our app.
    client_id = Bot.oauth["client_id"]
    scope = Bot.oauth["scope"]
    logging.info("INSTALLING | clinet_id: "+client_id+" and "+ scope)
    # Our template is using the Jinja templating language to dynamically pass
    # our client id and scope
    return render_template("install.html", client_id=client_id, scope=scope)


@app.route("/thanks", methods=["GET", "POST"])
def thanks():
    """
    This route is called by Slack after the user installs our app. It will
    exchange the temporary authorization code Slack sends for an OAuth token
    which we'll save on the bot object to use later.
    To let the user know what's happened it will also render a thank you page.
    """
    # Let's grab that temporary authorization code Slack's sent us from
    # the request's parameters.
    code_arg = request.args.get('code')
    logging.info("THANKS | code: "+code_arg)
    # The bot's auth method to handles exchanging the code for an OAuth token
    pyBot = Bot()
    pyBot.auth_new_team(code_arg)
    # Add the newly authorized bot to the list og our bots
    team_id = pyBot.get_team_id()
    bot_token = pyBot.get_bot_token()
    
    logging.info("Adding new authorized bot for team: <"+team_id+"> : <"+bot_token+">")
    team_bots[team_id] = pyBot

    # Let's try the DB now
    logging.info("Trying to crate the team approval object")
    teamApproval = TeamApproval(
        team_id=team_id,
        authorization_token=bot_token,
        timestamp=datetime.datetime.utcnow()
    )

    logging.info("Trying to add team approval to DB...")
    db.session.merge(teamApproval)
    db.session.commit()

    #give participant object access to the respective bots
    #update_participants_bots()

    return render_template("thanks.html")

@app.route("/listening", methods=["GET", "POST"])
def hears():
    """
    This route listens for incoming events from Slack and uses the event
    handler helper function to route events to our Bot.
    """
    logging.info("Got an event from slack!")
    slack_event = json.loads(request.data)
    for key, value in slack_event.items():
        logging.info("Key: "+str(key) +", Value: "+str(value))

    logging.info("After trying to writ eht listening stuff...")
    # ============= Slack URL Verification ============ #
    # In order to verify the url of our endpoint, Slack will send a challenge
    # token in a request and check for this token in the response our endpoint
    # sends back.
    #       For more info: https://api.slack.com/events/url_verification
    if "challenge" in slack_event:
        return make_response(slack_event["challenge"], 200, {"content_type":
                                                             "application/json"
                                                             })

    # ============ Slack Token Verification =========== #
    # We can verify the request is coming from Slack by checking that the
    # verification token in the request matches our app's settings
    if Bot.verification != slack_event.get("token"):
        message = "Invalid Slack verification token: %s \npyBot has: \
                   %s\n\n" % (slack_event["token"], Bot.verification)
        # By adding "X-Slack-No-Retry" : 1 to our response headers, we turn off
        # Slack's automatic retries during development.
        make_response(message, 403, {"X-Slack-No-Retry": 1})

    # ====== Process Incoming Events from Slack ======= #
    # If the incoming request is an Event we've subcribed to
    if "event" in slack_event:
        event_type = slack_event["event"]["type"]
        logging.info("Event is of type: "+event_type)
        print("Slack event: ", event_type)
        # Then handle the event by event_type and have your bot respond
        return _event_handler(event_type, slack_event)
    # If our bot hears things that are not events we've subscribed to,
    # send a quirky but helpful error response
    return make_response("[NO EVENT IN SLACK REQUEST] These are not the droids\
                         you're looking for.", 404, {"X-Slack-No-Retry": 1})

@app.route("/admin", methods=["GET", "POST"])
def admin_view():
    team_approvals = TeamApproval.query.order_by(sqlalchemy.desc(TeamApproval.timestamp)).limit(10)
    survey_question_log = SurveyQuestionLog.query.order_by(sqlalchemy.desc(SurveyQuestionLog.timestamp)).limit(50)
    study_participants = Participant.query.order_by(sqlalchemy.desc(Participant.time_added)).limit(30)

    #get survey schemas
    surveys = Survey.query.order_by(sqlalchemy.asc(Survey.id)).limit(10)
    #get questions for these surveys
    questions = SurveyQuestion.query.order_by(sqlalchemy.asc(SurveyQuestion.id)).limit(30)
    #get survey schedules
    schedules = SurveySchedule.query.order_by(sqlalchemy.asc(SurveySchedule.id)).limit(30)
    #get participant - survey assigment
    surveyAssignments = ParticipantSurveyAssignment.query.order_by(sqlalchemy.asc(ParticipantSurveyAssignment.id)).limit(30)

    return render_template("admin.html", 
        study_participants=study_participants, 
        team_approvals=team_approvals, 
        survey_question_log=survey_question_log,
        survey_schemas=surveys,
        survey_questions=questions,
        survey_schedules=schedules,
        participant_survey_assignment=surveyAssignments)
    #return output, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route("/getSlackTeamMembers", methods=["GET", "POST"])
def get_slack_team_members():
    logging.info("Asked for slack team members...")
    team_id = request.args.get('team_id') #request.form['text']
    logging.info("Team id <{}> members".format(team_id))

    team_members = []
    if team_id in team_bots:
        team_members = team_bots[team_id].get_users_in_team()

    return render_template("team_members.html", team_id=team_id, team_members=team_members)    

@app.route("/getReflectiveQuestion", methods=["GET", "POST"])
def get_reflective_question():
    logging.info("Asked to generate question...")
    alexa_device_id = request.args.get('device_id') #request.form['text']
    logging.info("A question for device_id: {}".format(alexa_device_id))

    questions = {
        "amzn1.ask.device.AEX5M7GZOVQIO5TWUZS2HQEIY5JTUWL4KEBEXBKBP52QP4C4T4WXBO4M7XDXQHMZUSX7GNRNSIZURSKIKP52YE4QRYV2XKNSUH7BVS4P6HJULBJGX27QOGBBJYV5JBXTYIOOKWBXMLQH4P5JREHEOAQ2ZWUQ": "What did you learn at work today?",
        "amzn1.ask.device.AEX5M7GZOVQIO5TWUZS2HQEIY5JU3J57KRJUR5QWHULRUU3LEHNHI6GTNEJM5L2H6VPTNG52ZZ4572YK73XQP6MFXOJTFKTAXZCAAILLZKG6MMHGUA5WD2L5YV553PM4N7TG4DLL7YMPQKB27QU5ZZWKBLGQ": "Why are you still working on reflection? What is the value of that?"
    }

    json_enc_question = json.dumps({}) # empty response if something went wrong, is handled on the Alexa side now
    if alexa_device_id in questions:
        json_enc_question = json.dumps({'question_text': questions[alexa_device_id]})
    
    return make_response(json_enc_question, 200, {"content_type":"application/json"})

@app.route("/setReflectionResponse", methods=["GET", "POST"])
def log_reflection_response():
    logging.info("Asked to log reflection response...")
    alexa_device_id = request.args.get('device_id') #request.form['text']
    reflection_text = request.args.get('text')

    logging.info("Got a reflection response from Alexa text:{}, device_id:{}".format(reflection_text, alexa_device_id))
    logging.info("Find the user this reflection response belongs to...")

    json_enc_question = json.dumps({}) # empty response if something went wrong, is handled on the Alexa side now

    user = Participant.query.filter_by(device_id=alexa_device_id).first()
    if user:
        user.send_dm_message("Hey, thanks for your reflection, you shared with us: "+reflection_text)
        surveyQuestionLog = SurveyQuestionLog(
                                user_id=user.id,
                                survey_id=None,
                                question_id=None,
                                question_type="REFLECTION_RESPONSE",
                                text=reflection_text)

        logging.info("Logging reflection response received to DB...")
        db.session.add(surveyQuestionLog)
        db.session.commit()

        json_enc_question = json.dumps({'logged': "OK"})

    else:
        logging.warning("Can't find matching user for reflective response, the device id is: "+alexa_device_id)


    return make_response(json_enc_question, 200, {"content_type":"application/json"})

@app.route("/sendBotMessage", methods=["GET", "POST"])
def send_bot_message():
    logging.info("Bot(s) will try to send a message now...")
    
    team_id = request.args.get('team_id')
    user_id = request.args.get('user_id')
    channel_id = request.args.get('channel_id')
    text = request.args.get('text') #request.form['text']

    logging.info("Got text to send: {}".format(text))

    if team_id is not None:
        logging.info("There is team_id provided: " + team_id)
        if team_id in team_bots:
            #post to specified channel
            if channel_id is not None:
                logging.info("Got channel id: "+channel_id)
                team_bots[team_id].post_message(channel_id, text)
            elif user_id is not None:
                logging.info("Got user id: "+user_id)
                channel_id = team_bots[team_id].open_dm(user_id)
                team_bots[team_id].post_message(channel_id, text)
            else:
                logging.info("No user id and no channel it, have to find the channel for bot!")
                bot_channels = team_bots[team_id].get_bot_channels()
                if len(bot_channels) > 0:
                    team_bots[team_id].post_message(bot_channels[0], text)
    else:
        #there is not team id, do default broadcast - NOT SURE THAT BROADCASE is a good design choice here!
        logging.info("Did not get the team id, so now just going through all the bots")
        for team_id, team_bot in team_bots.items():
            bot_channels = team_bot.get_bot_channels()
            if len(bot_channels) > 0:
                team_bot.post_message(bot_channels[0], text)

    return make_response("{}", 200, {"content_type":"application/json"})

@app.route("/updateParticipant", methods=["GET", "POST"])
def updte_participant():
    logging.info("Updating selected participant...")

    user_id = request.args.get('user_id')

    logging.info("User for update: {}".format(user_id))

    #1. Find the user
    logging.info("First trying to find the participant object...")
    participant = Participant.query.filter_by(id=user_id).first()
    if participant:
        logging.info("Participant object found!")
        participant.update()

        #update the participant in the DB
        db.session.commit()
    else:
        logging.warning("There is not participat object for this participant id: "+user_id)

    return make_response("{}", 200, {"content_type":"application/json"})


@app.route("/sendSurveyToParticipant", methods=["GET", "POST"])
def send_survey_to_participant():
    logging.info("Send survey to participant...")
    survey_id = request.args.get('survey_id')
    user_id = request.args.get('user_id')

    #update_participants_bots()

    logging.info("Checking bots for all the participants!!!!")
    study_participants = Participant.query.order_by(sqlalchemy.asc(Participant.time_added))
    for participant in study_participants:
        logging.info("Checking participant "+participant.id+", name: "+participant.name+", is_bot:" +str(participant.get_bot_reference() != None))

    # Let's try the DB now
    logging.info("Trying to send the survey to participant now, user_id:"+user_id+", survey_id:"+survey_id)
    
    #1. Find the user
    logging.info("First trying to find the participant object...")
    participant = Participant.query.filter_by(id=user_id).first()
    logging.info("Getting survey object...")
    survey = Survey.query.filter_by(id=survey_id).first()
    if participant:
        logging.info("Participant object found!")
        if survey:
            logging.info("Survey object found, callin send survey on participant!")
            participant.send_survey(survey)
    else:
        logging.warning("There is not participat object for this participant id: "+user_id)

    return make_response("{}", 200, {"content_type":"application/json"})

@app.route("/addStudyParticipant", methods=["GET", "POST"])
def add_study_participant():
    logging.info("Adding study participant now...")
    team_id = request.args.get('team_id')
    slack_id = request.args.get('slack_id')
    name = request.args.get('name')

    # Let's try the DB now
    logging.info("Trying to crate the participant object now")
    participant = Participant(
        team_id=team_id,
        slack_id=slack_id,
        name=name
    )

    logging.info("Trying to add participant to DB...")
    db.session.merge(participant)
    db.session.commit()

    return make_response("{}", 200, {"content_type":"application/json"})

@app.route("/assignParticipantToSurvey", methods=["GET", "POST"])
def assign_participant_to_survey():
    logging.info("Assigning participant to survey...")
    survey_id = request.args.get('survey_id')
    user_id = request.args.get('user_id')

    # Let's try the DB now
    logging.info("Trying to crate the participant object now, user_id:"+user_id+", survey_id:"+survey_id)

    participant_surveys = ParticipantSurveyAssignment.query.filter_by(user_id=user_id, survey_id=survey_id).first()
    if not participant_surveys:
        participantSurveyAssignment = ParticipantSurveyAssignment(
            survey_id=survey_id,
            user_id=user_id
        )

        logging.info("Trying to add participant to the survey in DB...")
        db.session.add(participantSurveyAssignment)
        db.session.commit()
    else:
        logging.info("Participant already assigned to survey, no need to assign again!")

    return make_response("{}", 200, {"content_type":"application/json"})

if __name__ == '__main__':
    logging.info("Loading the server, first load the already authorized team data")
    #DataMgr.load_team_auths()

    logging.info('Creating all database tables...')
    db.create_all()
    logging.info('Done!')
    
    ## Initialize a bot with atuhorization for each team
    logging.info("Create and authorize bot instance for each team we have:")
    #team_list = DataMgr.get_authed_teams()
    team_list = TeamApproval.query.order_by(sqlalchemy.desc(TeamApproval.timestamp)).limit(20)
    n = 1
    for team in team_list:
        team_id = team.id
        team_auth_token = team.authorization_token

        logging.info("TEAM["+str(n)+"] Key: "+str(team_id) +", Value: "+str(team_auth_token))

        teamBot = Bot()
        teamBot.auth_this_bot(team_id, team_auth_token)

        #add the bot to the list
        team_bots[team_id] = teamBot
        n=n+1

    logging.info("Start the actual server...")
    app.run(debug=True)
