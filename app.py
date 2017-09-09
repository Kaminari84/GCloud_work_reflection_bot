# -*- coding: utf-8 -*-
"""
A routing layer for the onboarding bot tutorial built using
[Slack's Events API](https://api.slack.com/events-api) in Python
"""
import logging
import uuid
import socket
import time
import json
import os
import base64
import urllib.request
from flask import Flask, request, make_response, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_, or_
import sqlalchemy
import requests

import random
from random import random, randrange
from datetime import datetime, timedelta

#from dataMgr import DataMgr
import dataMgr
from dataMgr import app
from dataMgr import db
from dataMgr import TeamApproval
from dataMgr import SurveyQuestionLog
from dataMgr import SurveyQuestion
from dataMgr import Survey
from dataMgr import SurveyLog
from dataMgr import SurveyReminderLog
from dataMgr import SurveySchedule
from dataMgr import ParticipantSurveyAssignment
from dataMgr import Participant
from dataMgr import ReflectiveQuestionAssignment
from dataMgr import ReflectiveQuestion
from dataMgr import AudioRecordingLog

#Import time helper functions
from dataMgr import utcnow
from dataMgr import pstnow
from dataMgr import generate_pacific_date

#Import bot global objects
from dataMgr import team_bots
from bot import Bot
from enum import Enum
from werkzeug.utils import secure_filename

logging.basicConfig(level=logging.INFO)

ALLOWED_EXTENSIONS = set(['txt', 'css', 'wav'])

def setup_app(app):
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

setup_app(app)

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
                    logging.info("Determined that should add message to log, now find the user object that should handle it")
                    participant = Participant.query.filter_by(team_id=team_id, slack_id=creator_id).first()
                    if participant:
                        logging.info("Participant object found to handle the message")
                        participant.handle_message(channel, message_text)
                        participant.update()
                    else:
                        logging.warning("No participant found that can handle this message!")
                        #team_bots[team_id].post_message(channel, "Hey I am just a work reflection study bot and you are not a participant. Would you like to join?")

        else:
            logging.warning("No bot found for the team id: <"+team_id+">")
        return make_response("I am responding to your message!", 200, )

    # ============= Event Type Not Found! ============= #
    # If the event_type does not have a handler
    message = "You have not added an event handler for the %s" % event_type
    # Return a helpful error message
    return make_response(message, 200, {"X-Slack-No-Retry": 1})

def get_per_day_report_data(user_id, start_date=None, weeks=None):
    user_name = None

    #determine the start and end date for the current week
    if user_id is not None:
        user = Participant.query.get(user_id)
        if user:
            user_name = user.name

    now = pstnow()
    if start_date is not None:
        now = start_date

    n_weeks = 1
    if weeks is not None:
        n_weeks = weeks

    today_week_day = now.weekday()
    sdate = generate_pacific_date(now.year, now.month, now.day, 0,0,0)
    edate = generate_pacific_date(now.year, now.month, now.day, 23,59,59)
    
    #decide on the shift of the dates from today to achieve the start and end of the week
    sdate = sdate + timedelta(days=-today_week_day)
    e_shift = n_weeks*7-today_week_day-3
    edate = edate + timedelta(days=e_shift)

    logging.info("sdate: "+ sdate.isoformat(' '))
    logging.info("edate: "+ edate.isoformat(' '))

    #put 7 days into a dictionary [date, week_day] "days"
    days = []
    weeks = {}
    act_date = sdate
    logging.info("Generating list of days")
    n = 1
    while act_date <= edate:
        if act_date.weekday() < 5:
            day_of_year = act_date.timetuple().tm_yday
            week_number = act_date.isocalendar()[1]
            logging.info("Act date: "+act_date.isoformat(' ')+", day_of_year: "+str(day_of_year))
            
            days.append({"id": n, 
                "date": act_date, 
                "weekday": act_date.weekday(),
                "day_of_year": day_of_year,
                "week_number": week_number })

            if week_number not in weeks and act_date.weekday() == 0:
                weeks[week_number] = {
                    "week_number": week_number,
                    "monday": act_date,
                    "friday": act_date + timedelta(days=5),
                    "sunday": act_date + timedelta(days=7)
                }

            n = n + 1
        act_date = act_date + timedelta(days=1)

    #put a list of survey questions into a dictionary "questions" [date, weekday, sl_id, sql_id]
    questions = []
    answers = []
    reflection_questions = []
    reflection_answers = []
    data_for_days = {}
    reflection_for_days = {}
    qn = 1
    an = 1
    survey_logs = SurveyLog.query.filter_by(user_id=user_id).filter(and_(SurveyLog.time_started>sdate,SurveyLog.time_started<edate)).all()
    for survey_log in survey_logs:
        day_of_year = survey_log.time_started.timetuple().tm_yday
        survey = Survey.query.get(survey_log.survey_id)
        if survey:
            if survey.type == "REPORT" or survey.type == "REFLECTION":
                #questions
                sql_qses = SurveyQuestionLog.query.filter_by(user_id=user_id, survey_log_id=survey_log.id, question_type="SURVEY_QUESTION").all()
                for sql_qs in sql_qses:
                    qtype = "Other"
                    if sql_qs.question_id % 10 == 1:
                        qtype = "Accomplishments"
                    elif sql_qs.question_id % 10 == 2:
                        qtype = "Plans"

                    questions.append({"id": qn, 
                        "date": sql_qs.timestamp, 
                        "weekday": sql_qs.timestamp.weekday(),
                        "type": survey.type,
                        "modality": survey.modality,
                        "survey_started": survey_log.time_started,
                        "day_of_year": day_of_year,
                        "s_id": survey.id,
                        "sl_id": survey_log.id, 
                        "sql_id": sql_qs.question_id, 
                        "text": sql_qs.text,
                        "qtype": qtype})

                    if survey.type == "REPORT":
                        logging.info("Question ["+str(n)+"] - date:"+sql_qs.timestamp.isoformat(' ')+
                            ", day_of_year: "+str(sql_qs.timestamp.timetuple().tm_yday)+", text: "+sql_qs.text+
                            ", sl_id: "+str(survey_log.id)+", sql_id: "+str(sql_qs.id))
                    elif survey.type == "REFLECTION":
                        logging.info("Reflection Question ["+str(n)+"] - date:"+sql_qs.timestamp.isoformat(' ')+
                            ", day_of_year: "+str(sql_qs.timestamp.timetuple().tm_yday)+", text: "+sql_qs.text+
                            ", sl_id: "+str(survey_log.id)+", sql_id: "+str(sql_qs.id))
                    qn = qn + 1

                #answers
                sql_ases = []
                if survey.type == "REPORT":
                    sql_ases = SurveyQuestionLog.query.filter_by(user_id=user_id, survey_log_id=survey_log.id, question_type="USER_MESSAGE").all()
                elif survey.type == "REFLECTION":
                    #answers
                    sql_ases = SurveyQuestionLog.query.filter(
                        and_(SurveyQuestionLog.user_id==user_id, 
                        SurveyQuestionLog.survey_log_id==survey_log.id, 
                            or_(SurveyQuestionLog.question_type=="USER_MESSAGE", SurveyQuestionLog.question_type=="USER_VOICE_MESSAGE") 
                        ) 
                    ).all()

                for sql_as in sql_ases:
                    qtype = "Other"
                    if sql_as.question_id % 10 == 1:
                        qtype = "Accomplishments"
                    elif sql_as.question_id % 10 == 2:
                        qtype = "Plans"

                    txt_list = sql_as.text.split("\n")
                    i = 0
                    logging.info("Split list:")
                    for txt_item in txt_list:
                        logging.info("["+str(i)+"]:"+txt_item)
                        answers.append({"id": an, 
                            "split_n": i,
                            "date": sql_as.timestamp, 
                            "weekday": sql_as.timestamp.weekday(),
                            "type": survey.type,
                            "modality": survey.modality,
                            "survey_started": survey_log.time_started,
                            "day_of_year": day_of_year,
                            "s_id": survey.id,
                            "sl_id": survey_log.id, 
                            "sql_id": sql_as.question_id, 
                            "text": txt_item,
                            "qtype": qtype})
                        i=i+1
                    
                    if survey.type == "REPORT":
                        #some data
                        if day_of_year in data_for_days:
                            data_for_days[day_of_year].append(sql_as.text)
                        else:
                            data_for_days[day_of_year] = []
                            data_for_days[day_of_year].append(sql_as.text)

                        logging.info("Answers ["+str(n)+"] - date:"+sql_as.timestamp.isoformat(' ')+
                            ", day_of_year: "+str(day_of_year)+", text: "+sql_as.text+
                            ", sl_id: "+str(survey_log.id)+", sql_id: "+str(sql_qs.id))
                    
                    elif survey.type == "REFLECTION":
                        #some reflection
                        if day_of_year in reflection_for_days:
                            reflection_for_days[day_of_year].append(sql_as.text)
                        else:
                            reflection_for_days[day_of_year] = []
                            reflection_for_days[day_of_year].append(sql_as.text)

                        logging.info("Reflection Answers ["+str(n)+"] - date:"+sql_as.timestamp.isoformat(' ')+
                            ", day_of_year: "+str(day_of_year)+", text: "+sql_as.text+
                            ", sl_id: "+str(survey_log.id)+", sql_id: "+str(sql_as.id))
                    an = an + 1
    
    for day in days:
        day["is_data"] = 0
        day['is_reflection'] = 0
        day['is_past'] = 0
        pnow = pstnow()
        if generate_pacific_date(pnow.year, pnow.month, pnow.day, 23,59,59) > day['date']:
            day['is_past'] = 1
        
        if day["day_of_year"] in data_for_days:
            day["is_data"] = 1
        if day["day_of_year"] in reflection_for_days:
            day['is_reflection'] = 1
        logging.info("Checking day: "+str(day['day_of_year'])+", data: "+str(day["is_data"])+", reflection: "+str(day["is_reflection"])+", passed: "+str(day['is_past']))

    return {"user_name": user_name,
            "start_date": sdate, 
            "end_date": edate,
            "days": days,
            "weeks": weeks,
            "questions": questions,
            "answers": answers}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_file', methods=["GET", "POST"])
def upload_file():
    logging.info("Called file upload!")
    
    json_enc_question = json.dumps({})
    # check if the post request has the file part
    if 'file' not in request.files:
        logging.warning("No file in request!")
        json_resp = json.dumps({
            'status': 'error',
            'message': 'no file part for upload!'})
      
        return make_response(json_resp, 200, {"content_type":"application/json"})
    
    file = request.files['file']
    if file.filename == '':
        logging.warning("Empty file in request!")
        json_resp = json.dumps({
            'status': 'error',
            'message': 'empty file specified for upload!'})
        return make_response(json_resp, 200, {"content_type":"application/json"})

    if file and allowed_file(file.filename):
        logging.info("File <"+file.filename+">seems correct, trying to upload...")
        filename = secure_filename(file.filename)
        file.save(filename)
        json_resp = json.dumps({
            'status': 'OK',
            'message': 'uploading file: <'+filename+'>'})
        return make_response(json_resp, 200, {"content_type":"application/json"})
    else:
        logging.warning("Apparently file not allowed: "+file.filename)
        json_resp = json.dumps({
            'status': 'error',
            'message': 'file type not allowed!'})
        return make_response(json_resp, 200, {"content_type":"application/json"})    

@app.route('/visualization', methods=["GET", "POST"])
def graphical_dashboard():
    logging.info("Opening visualization")
    user_id = request.args.get('user_id')

    start_log_date = generate_pacific_date(2017, 8, 14, 0,0,0)
    earliest_log = SurveyLog.query.filter_by(user_id=user_id).order_by(sqlalchemy.asc(SurveyLog.time_started)).first()
    if earliest_log:
        start_log_date = earliest_log.time_started
        logging.info("Found earliest log date: "+start_log_date.isoformat(' '))

    if user_id == "T045J3UQY_U5X1GJG06":
        start_log_date = generate_pacific_date(2017, 8, 21, 0,0,0)

    data = get_per_day_report_data(user_id, start_log_date, 3)

    #group reflective questions
    logging.info("Grouping reflective questions...")
    group_reflective = {}
    gr_n = 0
    for question in data['questions']:
        if question['type'] == "REFLECTION":
            logging.info("Question id: "+str(question['sql_id'])+", day: "+str(question['day_of_year'])+", text: "+question['text'])
            gr_id = str(question['day_of_year'])+"_"+question['text']
            if gr_id not in group_reflective:
                logging.info("Text not yet in, adding...")
                group_reflective[gr_id] = {
                    "id": gr_n,
                    "day_of_year": question['day_of_year'],
                    "sql_id": question['sql_id'],
                    "modality": question['modality'],
                    "type": question['type'],
                    "text": question['text']
                }
                gr_n = gr_n+1

    logging.info("Got weeks:")
    for key, week in data['weeks'].items():
        logging.info("Week ["+str(key)+"]->"+str(week['week_number'])+", monday:"+week['monday'].isoformat(' '))  

    # extract audio recordings
    logging.info("Extracting audio recordings...")
    audio_recs = AudioRecordingLog.query.filter_by(user_id=user_id).filter(and_(AudioRecordingLog.timestamp>data['start_date'], AudioRecordingLog.timestamp<data['end_date'])).order_by(sqlalchemy.asc(AudioRecordingLog.timestamp)).all()
    audio_recordings = []
    for audio_rec in audio_recs:
        logging.info("adding extracted audio recording...")

        timestamp = audio_rec.timestamp

        audio_recordings.append({
            "id": audio_rec.id,
            "timestamp": timestamp,
            "q_day_of_year": audio_rec.rq_date.timetuple().tm_yday,
            "day_of_year": timestamp.timetuple().tm_yday,
            'rq_id': audio_rec.rq_id,
            "rqa_id": audio_rec.rqa_id,
            'rq_date': audio_rec.rq_date,
            "audio_url": audio_rec.audio_url
            })

    return render_template('graphical_report2.html',
        user_id = user_id,
        participant_name = data['user_name'], 
        start_date = data['start_date'], 
        end_date = data['end_date'],
        weeks = data['weeks'],
        days = data['days'],
        questions = data['questions'],
        answers = data['answers'],
        reflective_questions_grouped = group_reflective,
        audio_recordings = audio_recordings)

    #return render_template('index.html')

@app.route('/by_day_dashboard', methods=["GET", "POST"])
def by_day_text_dashboard():
    logging.info("Opening user dashboard")
    user_id = request.args.get('user_id')
    sdate_temp = request.args.get('start_date')
    weeks_temp = request.args.get('weeks')

    start_date = sdate_temp
    if sdate_temp is not None:
        start_date = datetime.strptime(start_date,'%Y-%m-%d')
        logging.info("Start date in app.route: "+str(start_date.isoformat(' ')))
    else:
        earliest_log = SurveyLog.query.filter_by(user_id=user_id).order_by(sqlalchemy.asc(SurveyLog.time_started)).first()
        if earliest_log:
            start_date = earliest_log.time_started
            logging.info("Found earliest log date: "+start_date.isoformat(' '))


    weeks = weeks_temp
    if weeks_temp is not None:
        weeks = int(weeks_temp)
        logging.info("Weeks: "+str(weeks))
    
    data = get_per_day_report_data(user_id, start_date, weeks)

    #if user_id is not None:
    #    #go through the survey log
    #    survey_log = SurveyLog.query.filter_by(user_id=user_id).

    return render_template('report_by_day_type.html', 
        participant_name = data['user_name'], 
        start_date = data['start_date'], 
        end_date = data['end_date'],
        days = data['days'],
        questions = data['questions'],
        answers = data['answers'])

    #return render_template('index.html')

@app.route('/dashboard', methods=["GET", "POST"])
def by_question_text_dashboard():
    logging.info("Opening user dashboard")
    user_id = request.args.get('user_id')
    sdate_temp = request.args.get('start_date')
    weeks_temp = request.args.get('weeks')

    start_date = sdate_temp
    if sdate_temp is not None:
        start_date = datetime.strptime(start_date,'%Y-%m-%d')
        logging.info("Start date in app.route: "+str(start_date.isoformat(' ')))
    else:
        earliest_log = SurveyLog.query.filter_by(user_id=user_id).order_by(sqlalchemy.asc(SurveyLog.time_started)).first()
        if earliest_log:
            start_date = earliest_log.time_started
            logging.info("Found earliest log date: "+start_date.isoformat(' '))

    weeks = weeks_temp
    if weeks_temp is not None:
        weeks = int(weeks_temp)
        logging.info("Weeks: "+str(weeks))

    #data = get_per_question_report_data(user_id) #get_per_question_report_data(user_id)
    data = get_per_day_report_data(user_id, start_date, weeks)

    #group the questions by id
    question_texts = {}
    question_types = {}
    question_days = []
    question_type_days = {}
    qgn = 1
    qtype_n = 1 
    dn = 1
    qtype_dn = 1
    logging.info("Grouping questions...")
    for question in data['questions']:
        logging.info("Question id: "+str(question['sql_id'])+", text: "+question['text'])
        
        # Grouping by raw question text
        if question['sql_id'] not in question_texts:
            logging.info("Text not yet in, adding...")
            question_texts[question['sql_id']] = {
                "id": qgn,
                "sql_id": question['sql_id'],
                "type": question['type'],
                "text": question['text']
            }
            qgn = qgn + 1
            
        # Grouping by Accomplishments and Plans
        logging.info("Determine if it is an accomplishments or a plan question?")
        qtype = "Other"
        if question['sql_id'] % 10 == 1:
            qtype = "Accomplishments"
        elif question['sql_id'] % 10 == 2:
            qtype = "Plans"

        if qtype not in question_types:
            logging.info("Question type: "+qtype+" not yet in, adding...")
            question_types[qtype] = {
                "id": qtype_n,
                "type": question['type'],
                "qtype": qtype
            }
            qtype_n = qtype_n + 1

        # Assumption that the exact same text of the question will not be asked more than once a day
        logging.info("Adding day: "+question['date'].isoformat(' ')+", q_id: "+str(question['sql_id']))
        question_days.append({
                "id": dn,
                "date": question['date'],
                "day_of_year": question['day_of_year'],
                "sl_id": question['sl_id'],
                "sql_id": question['sql_id'],
            })
        dn = dn+1

        #shift the dates here
        qdate = question['date']
        qday_day_of_the_year = question['day_of_year']
        logging.info("Survey id for question: "+str(question['s_id']))
        #shift dates - morning survey
        if question['s_id'] == 1:
            if qtype == "Accomplishments":
                logging.info("Shifting day of year for survey_id: "+str(question['s_id'])+", qtype: "+qtype+", from: "+str(qday_day_of_the_year))
                qday_day_of_the_year = (question['survey_started'] - timedelta(days=1)).timetuple().tm_yday
                qdate = qdate - timedelta(days=1)
                logging.info("To: "+str(qday_day_of_the_year))
        #shift dates - end_of_day survey
        if question['s_id'] == 3:
            if qtype == "Plans":
                logging.info("Shifting day of year for survey_id: "+str(question['s_id'])+", qtype: "+qtype+", from: "+str(qday_day_of_the_year))
                qday_day_of_the_year = (question['survey_started'] + timedelta(days=1)).timetuple().tm_yday
                qdate = qdate + timedelta(days=1)
                logging.info("To: "+str(qday_day_of_the_year))
        
        #Unlikely, but same type of the question can be asked more than once a day
        dkey = str(qday_day_of_the_year)+"_"+qtype
        if dkey not in question_type_days:
            logging.info("Adding qtype day: "+question['date'].isoformat(' ')+", qtype: "+qtype)
            question_type_days[dkey] = {
                "id": qtype_dn,
                "date": qdate,
                "day_of_year": qday_day_of_the_year,
                "qtype": qtype
            }
            qtype_dn = qtype_dn+1

    logging.info("Grouping answers...")
    answers_types = []
    for answer in data['answers']:
        logging.info("Answer id: "+str(answer['sql_id'])+", text: "+answer['text'])

        logging.info("Determine if it is a accomplishments or plans answer?")
        qtype = "Other"
        if answer['sql_id'] % 10 == 1:
            qtype = "Accomplishments"
        elif answer['sql_id'] % 10 == 2:
            qtype = "Plans"

        #shift the dates here
        qdate = answer['date']
        qday_day_of_the_year = answer['day_of_year']
        logging.info("Survey id for question: "+str(answer['s_id']))
        #shift dates - morning survey
        if answer['s_id'] == 1:
            if qtype == "Accomplishments":
                logging.info("Shifting day of year for survey_id: "+str(answer['s_id'])+", qtype: "+qtype+", from: "+str(qday_day_of_the_year))
                qday_day_of_the_year = (answer['survey_started'] - timedelta(days=1)).timetuple().tm_yday
                qdate = qdate - timedelta(days=1)
                logging.info("To: "+str(qday_day_of_the_year))
        #shift dates - end_of_day survey
        if answer['s_id'] == 3:
            if qtype == "Plans":
                logging.info("Shifting day of year for survey_id: "+str(answer['s_id'])+", qtype: "+qtype+", from: "+str(qday_day_of_the_year))
                qday_day_of_the_year = (answer['survey_started'] + timedelta(days=1)).timetuple().tm_yday
                qdate = qdate + timedelta(days=1)
                logging.info("To: "+str(qday_day_of_the_year))
        
        answers_types.append({"id": answer['id'], 
                            "split_n": answer['split_n'],
                            "date": qdate, 
                            "type": answer['type'],
                            "day_of_year": qday_day_of_the_year,
                            "sl_id": answer['sl_id'], 
                            "sql_id": answer['sql_id'], 
                            "text": answer['text'],
                            "qtype": qtype })

    logging.info("We have the following dictionary of questions:")
    for key, val in question_types.items():
        logging.info("Key: "+str(key)+", Val: "+val['qtype'])

    logging.info("We have the following question type days:")
    for key, val in question_type_days.items():
        logging.info("Key: "+str(key)+", Day of year: "+str(val['day_of_year'])+", qtype: "+val['qtype'])

    logging.info("Having answer types...")
    for answer_type in answers_types:
        logging.info("Qtype: "+answer_type['qtype']+", day_of_year: "+str(answer_type['day_of_year'])+", text: "+answer_type['text'])


    #if user_id is not None:
    #    #go through the survey log
    #    survey_log = SurveyLog.query.filter_by(user_id=user_id).

    '''
    return render_template('report_by_question_text.html', 
        participant_name = data['user_name'], 
        start_date = data['start_date'], 
        end_date = data['end_date'],
        days = question_days,
        questions = question_texts,
        answers = data['answers']
        )
    '''

    return render_template('report_by_question_type.html', 
        participant_name = data['user_name'], 
        start_date = data['start_date'], 
        end_date = data['end_date'],
        days = question_type_days,
        questions = question_types,
        answers = answers_types
        )
    #return render_template('index.html')

@app.route('/dashboard2', methods=["GET", "POST"])
def by_question_text_dashboard2():
    logging.info("Opening user dashboard")
    user_id = request.args.get('user_id')
    sdate_temp = request.args.get('start_date')
    weeks_temp = request.args.get('weeks')

    start_date = sdate_temp
    if sdate_temp is not None:
        start_date = datetime.strptime(start_date,'%Y-%m-%d')
        logging.info("Start date in app.route: "+str(start_date.isoformat(' ')))
    else:
        earliest_log = SurveyLog.query.filter_by(user_id=user_id).order_by(sqlalchemy.asc(SurveyLog.time_started)).first()
        if earliest_log:
            start_date = earliest_log.time_started
            logging.info("Found earliest log date: "+start_date.isoformat(' '))

    weeks = weeks_temp
    if weeks_temp is not None:
        weeks = int(weeks_temp)
        logging.info("Weeks: "+str(weeks))

    #data = get_per_question_report_data(user_id) #get_per_question_report_data(user_id)
    data = get_per_day_report_data(user_id, start_date, weeks)

    #group the questions by id
    question_texts = {}
    question_types = {}
    question_days = []
    question_type_days = {}
    qgn = 1
    qtype_n = 1 
    dn = 1
    qtype_dn = 1
    logging.info("Grouping questions...")
    for question in data['questions']:
        logging.info("Question id: "+str(question['sql_id'])+", text: "+question['text'])
        
        # Grouping by raw question text
        if question['sql_id'] not in question_texts:
            logging.info("Text not yet in, adding...")
            question_texts[question['sql_id']] = {
                "id": qgn,
                "sql_id": question['sql_id'],
                "type": question['type'],
                "text": question['text']
            }
            qgn = qgn + 1
            
        # Grouping by Accomplishments and Plans
        logging.info("Determine if it is an accomplishments or a plan question?")
        qtype = "Other"
        if question['sql_id'] % 10 == 1:
            qtype = "Accomplishments"
        elif question['sql_id'] % 10 == 2:
            qtype = "Plans"

        if qtype not in question_types:
            logging.info("Question type: "+qtype+" not yet in, adding...")
            question_types[qtype] = {
                "id": qtype_n,
                "type": question['type'],
                "qtype": qtype
            }
            qtype_n = qtype_n + 1

        # Assumption that the exact same text of the question will not be asked more than once a day
        logging.info("Adding day: "+question['date'].isoformat(' ')+", q_id: "+str(question['sql_id']))
        question_days.append({
                "id": dn,
                "date": question['date'],
                "day_of_year": question['day_of_year'],
                "sl_id": question['sl_id'],
                "sql_id": question['sql_id'],
            })
        dn = dn+1

        #shift the dates here
        qdate = question['date']
        qday_day_of_the_year = question['day_of_year']
        logging.info("Survey id for question: "+str(question['s_id']))
        #shift dates - morning survey
        if question['s_id'] == 1:
            if qtype == "Accomplishments":
                logging.info("Shifting day of year for survey_id: "+str(question['s_id'])+", qtype: "+qtype+", from: "+str(qday_day_of_the_year))
                qday_day_of_the_year = (question['survey_started'] - timedelta(days=1)).timetuple().tm_yday
                qdate = qdate - timedelta(days=1)
                logging.info("To: "+str(qday_day_of_the_year))
        #shift dates - end_of_day survey
        if question['s_id'] == 3:
            if qtype == "Plans":
                logging.info("Shifting day of year for survey_id: "+str(question['s_id'])+", qtype: "+qtype+", from: "+str(qday_day_of_the_year))
                qday_day_of_the_year = (question['survey_started'] + timedelta(days=1)).timetuple().tm_yday
                qdate = qdate + timedelta(days=1)
                logging.info("To: "+str(qday_day_of_the_year))
        
        #Unlikely, but same type of the question can be asked more than once a day
        dkey = str(qday_day_of_the_year)+"_"+qtype
        if dkey not in question_type_days:
            logging.info("Adding qtype day: "+question['date'].isoformat(' ')+", qtype: "+qtype)
            question_type_days[dkey] = {
                "id": qtype_dn,
                "date": qdate,
                "day_of_year": qday_day_of_the_year,
                "qtype": qtype
            }
            qtype_dn = qtype_dn+1

    logging.info("Grouping answers...")
    answers_types = []
    for answer in data['answers']:
        logging.info("Answer id: "+str(answer['sql_id'])+", text: "+answer['text'])

        logging.info("Determine if it is a accomplishments or plans answer?")
        qtype = "Other"
        if answer['sql_id'] % 10 == 1:
            qtype = "Accomplishments"
        elif answer['sql_id'] % 10 == 2:
            qtype = "Plans"

        #shift the dates here
        qdate = answer['date']
        qday_day_of_the_year = answer['day_of_year']
        logging.info("Survey id for question: "+str(answer['s_id']))
        #shift dates - morning survey
        if answer['s_id'] == 1:
            if qtype == "Accomplishments":
                logging.info("Shifting day of year for survey_id: "+str(answer['s_id'])+", qtype: "+qtype+", from: "+str(qday_day_of_the_year))
                qday_day_of_the_year = (answer['survey_started'] - timedelta(days=1)).timetuple().tm_yday
                qdate = qdate - timedelta(days=1)
                logging.info("To: "+str(qday_day_of_the_year))
        #shift dates - end_of_day survey
        if answer['s_id'] == 3:
            if qtype == "Plans":
                logging.info("Shifting day of year for survey_id: "+str(answer['s_id'])+", qtype: "+qtype+", from: "+str(qday_day_of_the_year))
                qday_day_of_the_year = (answer['survey_started'] + timedelta(days=1)).timetuple().tm_yday
                qdate = qdate + timedelta(days=1)
                logging.info("To: "+str(qday_day_of_the_year))
        
        answers_types.append({"id": answer['id'], 
                            "split_n": answer['split_n'],
                            "date": qdate, 
                            "type": answer['type'],
                            "day_of_year": qday_day_of_the_year,
                            "sl_id": answer['sl_id'], 
                            "sql_id": answer['sql_id'], 
                            "text": answer['text'],
                            "qtype": qtype })

    logging.info("We have the following dictionary of questions:")
    for key, val in question_types.items():
        logging.info("Key: "+str(key)+", Val: "+val['qtype'])

    logging.info("We have the following question type days:")
    for key, val in question_type_days.items():
        logging.info("Key: "+str(key)+", Day of year: "+str(val['day_of_year'])+", qtype: "+val['qtype'])

    logging.info("Having answer types...")
    for answer_type in answers_types:
        logging.info("Qtype: "+answer_type['qtype']+", day_of_year: "+str(answer_type['day_of_year'])+", text: "+answer_type['text'])


    #if user_id is not None:
    #    #go through the survey log
    #    survey_log = SurveyLog.query.filter_by(user_id=user_id).

    return render_template('report_by_question_text.html', 
        participant_name = data['user_name'], 
        start_date = data['start_date'], 
        end_date = data['end_date'],
        days = question_days,
        questions = question_texts,
        answers = data['answers']
        )

@app.route('/', methods=["GET", "POST"])
def index():
    client_id = Bot.oauth["client_id"]
    scope = Bot.oauth["scope"]
    logging.info("INSTALLING | clinet_id: "+client_id+" and "+ scope)
    # Our template is using the Jinja templating language to dynamically pass
    # our client id and scope
    return render_template("install.html", client_id=client_id, scope=scope)


@app.route('/amazon_login', methods=["GET", "POST"])
def amazon_login():
    #https://developer.amazon.com/public/apis/engage/login-with-amazon/docs/obtain_customer_profile.html
    #https://developer.amazon.com/public/apis/engage/login-with-amazon/content/python_sample.html
    #https://developer.amazon.com/public/apis/engage/login-with-amazon/docs/customer_profile.html
    #https://layla.amazon.com/api/skill/link/M3PCI3IUJM071W
    #https://pitangui.amazon.com/api/skill/link/M3PCI3IUJM071W
    #https://layla.amazon.com/api/skill/link/M3PCI3IUJM071W
    
    output = "<b>Amazon login</b><br />"
    logging.info("OK, trying to do Amazon login...")

    raw_cookie = 'x-amzn-dat-gui-client-v=1.24.2418.0; aws-target-static-id=1500788346758-803460; s_vn=1532324347091%26vn%3D1; c_m=undefinedwww.google.comSearch%20Engine; appstore-devportal-locale=en_US; aws-session-id=145-5381310-8253451; aws-session-id-time=2132527939l; aws_lang=en; aws-target-visitor-id=1500788346766-484303.28_67; aws-target-data=%7B%22support%22%3A%221%22%7D; s_ppv=60; s_dslv=1501810035115; lc-main=en_US; __utmz=194891197.1502216791.14.9.utmccn=(referral)|utmcsr=console.aws.amazon.com|utmcct=/cloudwatch/home|utmcmd=referral; aws-ubid-main=134-4209745-4506065; aws-session-token="kZ59KXlrUs2FWAVKhhXr0/+Iyt9jR9LkBnxLbAvV2iuj+O0PLfCqq05tR2HWVg5rTuSDrM/9ZnRmDrxKW0FN6d1bdkxbvAgI+dYwW7lRpEJ00iVvhcM7HqE25fgO4zc4WxK3BobQgPPpZzkvW8ijgLLqWvqsGm5MrDCFiu40NnIYe6We0xNupohgcwkaCvvrzOE7uBu+dhYTrmf+0fraxLD/G6rA44Om1tPX3SZNodQ="; aws-x-main="nABOsbjLdqCgtKQvrLiSPrP1wyuKN85Pvv5UbrA16@RGxoN97QzdqeyiczTdJz1W"; aws-at-main=Atza|IwEBIDGOtJKMv9uO93iyx2QDUiXgzgBVYrmBVAuIpmjy-Ae8lUAxUmhRbIMQVJ80Df2zunyRPNZoz3qkcMfzXGQbObDv60F6Huf7OyGm-AUlihos0KoXQwnLxQLBLt9Bdc6rM35X20sFJnjlSZVM5zFHCNa4YwOdMCzTgdOrKd-2TxK5IPGTDDByBgc9FDb1dVB8INSGo8wuY7_6MnPekK3igco-Gq-N38qnAUNwkYOx5LOkGUlbyhSqBNMlQoF3u_8ertyBLBhjlFOfr6XYuUoCdh3peQ-KmuHQQ8P9isZIVLDGMYxpSdkJav8Z7fpLWUjbGTgkqM4a83SZXch_jZtKEJ92lK67J3JdVFuF8UVKruX-vOF5zXHZRD08xG_GTqN6wz9K9Xzyhs43swBXXXf1wRp7POJh2huy7YFGZkDPUXf_jA; sess-aws-at-main="KdD78wlLIiSdrxpr04a6j/yo/+x/7lbxCB6D9Jf3/l4="; aws-userInfo=%7B%22arn%22%3A%22arn%3Aaws%3Aiam%3A%3A052036420085%3Aroot%22%2C%22alias%22%3A%22%22%2C%22username%22%3A%22FXPAL%22%2C%22keybase%22%3A%22cPazaFBypQwdLWbe14YpXTPeBlMxuzbPjsKU0Z%2FGhn8%5Cu003d%22%2C%22issuer%22%3A%22https%3A%2F%2Fwww.amazon.com%2Fap%2Fsignin%22%7D; regStatus=registered; __utmv=194891197.%22nABOsbjLdqCgtKQvrLiSPrP1wyuKN85Pvv5UbrA16%40RGxoN97QzdqeyiczTdJz1W%22; __utma=194891197.460546855.1501807940.1502216818.1502226219.16; __utmc=194891197; skin=noskin; x-wl-uid=10gwRjOOAOytMeJ8vvNFLfumyhM9nfasBibe4y4qBhL6ztFROe/PIypcul/no6fC2+cjAOUOedE2lEjEdw39WEO7PVADMDE5qHq4jHAHHovC6vBY33r2za9Mn2QjFvGuwKuvZvUW9qMY=; csrf=-188564009; s_vnum=1504249200985%26vn%3D7; lwa-context=0362fa45139de719ce08b5243def1dba; session-id=138-5487301-8674609; session-id-time=2132969418l; s_cc=true; devportal-session=MnfySe0MMalj7kxdt+NwxbxJBYZehYrQaW7piaR5kUjCwtupUZvFwsP6OxbkYoAeQFSl4uIFT3xD03D+PaZKC8XAT/yQxBJzYzo3WE4NoqjnXn7SASBq3NKhIedjjoZLe0DjJbf+jskEM6MsqZ33vP7LwTgRjHPQxeEpzC5GUJuATrllwoY+yADkt0pnQ3YVncHDOZ9JD5eHwJYQasdFE7u7rBtiCwELbhnSqBoISuvJvYKQVYGhytzr/4N+9UpqWmA3jPVY2q/irpEiNdzNvZXVD72bnD7a6KMSprg1WhrUDbk56vA0vM37q/6UxE3X; s_sq=%5B%5BB%5D%5D; s_fid=0E1E85B30079EDB7-2E3D8DBDA6852F62; s_nr=1502251450239-Repeat; s_invisit=true; ubid-main=130-4095001-7074404; session-token="4yhZlamIcYrU1DZfYPvs1BhMs/rdHqX3cwYY+ZQq/1BA0VkLL1S8aOb07GrXq+a6of7SN4G4TU3kXluBLrLA4J42N8gaDvDtzJVFTsTS7U7JK+fuCncVADk5zj7mCeIXOPFFJhGVwjDH+rEa6ylTNaSGWWdwm0TG0HMytp2Xppg2V4dLp5aT9DVykPlNWQXm1RTi4MA4GhfJIz4jT7RHDuvpUsAwomENUTHQrEHKfXA="; x-main="9W63zN9UT1fP7wFFulrQCySiqyHDVCZRROtO4AEadXGqg?aKn8incXurOa?IV70B"; at-main=Atza|IwEBIHnnqJrZUR4M-Ck1rRAajJqg3bi5ISnhORofJZi_U_ZrfblII8LScm5a1FwPF5xvZFHfGB-NHG40DGiLdv0e7B0ZKvySzx8azeixIW3cKIaF1t6gicmHL94iOaIi1ypQjFcvRN016UCdvt_55topq16DxSBl4plbA3MR4I-gm0eursu9jOWsP7v8-WegvsNBSYqF4rd-tRYIZQc0Kb1hKDu7vgLfS2w9irVMuIqJFOVBVOjDB__YyFjys-wEHlzzQLuJS6SIzD2dCLsLTZjZjiQc2gaCiAp1GsCcEKAzUXo2vvwA6oiYPhNg2EDwPsJ7VbMsr2Mzfi0Do9bP-yJ9sjXv-lvS7ABDBvb6MddijwcAYLycEhBLYtI1yDH4PTwVmSKYGsreQ-kImbqGuK5IG5Qa; sess-at-main="bWzIO/RenrqL+mSNeL54fp5P7kRlzR9QtxF3DJtLUrI="'
    cookie = {}
    #output += "<h1>Cookie deconstruction:</h1><br />"
    for pair in raw_cookie.split(";"):
        key_val = pair.split("=")
        key = key_val[0]
        val = key_val[1]
        #output += "<ul>"
        #output += "<li><b>"+key+":</b>"+val+"</li>"
        #output += "</ul>"

        cookie[key] = val


    r = requests.post('https://pitangui.amazon.com/api/cards', cookies=cookie)
    output += "<h1>Website contents:</h1><br />"
    output += "<b>Status code: "+str(r.status_code)+"</b><br /><br />"
    output += "<b>Contents type: "+r.headers['content-type']+"</b><br /><br />"
    output += "<b>Encoding: "+r.encoding+"</b><br /><br />"
    output += "<b>Text: "+r.text+"</b><br /><br />"

    '''
    code = request.args.get('code')
    if code is None:
        logging.info("No code yet")
        output += "No code yet"

        #first request to get the temporary code
        args = dict(client_id="amzn1.application-oa2-client.76cca41f21d64c42ab2f48e13dcffc30",
                    scope="profile",
                    response_type="code",
                    redirect_uri="https://0fa29d53.ngrok.io/amazon_login",
                    )

        url_amazon = "https://www.amazon.com/ap/oa?"+urllib.parse.urlencode(args)
        logging.info("Callin amazon to get the code, url: "+url_amazon)
        return redirect(url_amazon, code=302)

    else:
        logging.info("We have the code, it is: "+code)
        output += "We have the code, it is: "+code

        client_id = "amzn1.application-oa2-client.76cca41f21d64c42ab2f48e13dcffc30"
        client_secret = "8583987be2bcebfac349c2fed93a168adc8f7326ea6227a6ab3724820e4384d9"

        #get the actual token for the future
        args = dict(client_id=client_id,
                    client_secret=client_secret,
                    grant_type="authorization_code",
                    code=code,
                    redirect_uri="https://0fa29d53.ngrok.io/amazon_login",
                    )

        try:
            my_request = urllib.request.Request("https://api.amazon.com/auth/o2/token", data=urllib.parse.urlencode(args).encode('utf-8'))
            my_request.add_header("Authorization", "Basic "+base64.b64encode((client_id + ":" + client_secret).encode('ascii')).decode("ascii"))
            my_response = urllib.request.urlopen(my_request)
            
            contents = my_response.read().decode('utf-8')
            logging.info("Got response: "+contents)

            output += "Contents: "+contents+"<br />"

            tokens = json.loads(contents)
            output += "<b>Access Token:</b>"+tokens['access_token']+"<br /><br />"
            output += "<b>Refresh Token:</b>"+tokens['refresh_token']+"<br /><br />"
            output += "<b>Token type:</b>"+tokens['token_type']+"<br /><br />"
            output += "<b>Expires in:</b>"+str(tokens['expires_in'])+"<br /><br />"

            #lets make a simple profile call
            args = dict(access_token=tokens['access_token'])
            profile_request = urllib.request.Request("https://api.amazon.com/user/profile?"+urllib.parse.urlencode(args))
            profile_response = urllib.request.urlopen(profile_request)
            #info = urllib.response.info()

            contents = profile_response.read().decode('utf-8')
            logging.info("Got response: "+contents)

            output += "<b>Profile:</b>"+contents+"<br /><br />"


            #lets make a simple profile call
            logging.info("------TRYING TO GET CARDS------")
            #args = dict(access_token=tokens['access_token'])
            #profile_request = urllib.request.Request("https://pitangui.amazon.com/api/cards?"+urllib.parse.urlencode(args))
            #profile_response = urllib.request.urlopen(profile_request)
            #info = urllib.response.info()

            #contents = profile_response.read().decode('utf-8')
            #logging.info("Got response: "+contents)

            #output += "<b>Profile:</b>"+contents+"<br /><br />"

            raw_cookie = 'x-amzn-dat-gui-client-v=1.24.2418.0; aws-target-static-id=1500788346758-803460; s_vn=1532324347091%26vn%3D1; c_m=undefinedwww.google.comSearch%20Engine; appstore-devportal-locale=en_US; aws-session-id=145-5381310-8253451; aws-session-id-time=2132527939l; aws_lang=en; aws-target-visitor-id=1500788346766-484303.28_67; aws-target-data=%7B%22support%22%3A%221%22%7D; s_ppv=60; s_dslv=1501810035115; lc-main=en_US; __utmz=194891197.1502216791.14.9.utmccn=(referral)|utmcsr=console.aws.amazon.com|utmcct=/cloudwatch/home|utmcmd=referral; aws-ubid-main=134-4209745-4506065; aws-session-token="kZ59KXlrUs2FWAVKhhXr0/+Iyt9jR9LkBnxLbAvV2iuj+O0PLfCqq05tR2HWVg5rTuSDrM/9ZnRmDrxKW0FN6d1bdkxbvAgI+dYwW7lRpEJ00iVvhcM7HqE25fgO4zc4WxK3BobQgPPpZzkvW8ijgLLqWvqsGm5MrDCFiu40NnIYe6We0xNupohgcwkaCvvrzOE7uBu+dhYTrmf+0fraxLD/G6rA44Om1tPX3SZNodQ="; aws-x-main="nABOsbjLdqCgtKQvrLiSPrP1wyuKN85Pvv5UbrA16@RGxoN97QzdqeyiczTdJz1W"; aws-at-main=Atza|IwEBIDGOtJKMv9uO93iyx2QDUiXgzgBVYrmBVAuIpmjy-Ae8lUAxUmhRbIMQVJ80Df2zunyRPNZoz3qkcMfzXGQbObDv60F6Huf7OyGm-AUlihos0KoXQwnLxQLBLt9Bdc6rM35X20sFJnjlSZVM5zFHCNa4YwOdMCzTgdOrKd-2TxK5IPGTDDByBgc9FDb1dVB8INSGo8wuY7_6MnPekK3igco-Gq-N38qnAUNwkYOx5LOkGUlbyhSqBNMlQoF3u_8ertyBLBhjlFOfr6XYuUoCdh3peQ-KmuHQQ8P9isZIVLDGMYxpSdkJav8Z7fpLWUjbGTgkqM4a83SZXch_jZtKEJ92lK67J3JdVFuF8UVKruX-vOF5zXHZRD08xG_GTqN6wz9K9Xzyhs43swBXXXf1wRp7POJh2huy7YFGZkDPUXf_jA; sess-aws-at-main="KdD78wlLIiSdrxpr04a6j/yo/+x/7lbxCB6D9Jf3/l4="; aws-userInfo=%7B%22arn%22%3A%22arn%3Aaws%3Aiam%3A%3A052036420085%3Aroot%22%2C%22alias%22%3A%22%22%2C%22username%22%3A%22FXPAL%22%2C%22keybase%22%3A%22cPazaFBypQwdLWbe14YpXTPeBlMxuzbPjsKU0Z%2FGhn8%5Cu003d%22%2C%22issuer%22%3A%22https%3A%2F%2Fwww.amazon.com%2Fap%2Fsignin%22%7D; regStatus=registered; __utmv=194891197.%22nABOsbjLdqCgtKQvrLiSPrP1wyuKN85Pvv5UbrA16%40RGxoN97QzdqeyiczTdJz1W%22; __utma=194891197.460546855.1501807940.1502216818.1502226219.16; __utmc=194891197; skin=noskin; x-wl-uid=10gwRjOOAOytMeJ8vvNFLfumyhM9nfasBibe4y4qBhL6ztFROe/PIypcul/no6fC2+cjAOUOedE2lEjEdw39WEO7PVADMDE5qHq4jHAHHovC6vBY33r2za9Mn2QjFvGuwKuvZvUW9qMY=; csrf=-188564009; s_vnum=1504249200985%26vn%3D7; lwa-context=0362fa45139de719ce08b5243def1dba; session-id=138-5487301-8674609; session-id-time=2132969418l; s_cc=true; devportal-session=MnfySe0MMalj7kxdt+NwxbxJBYZehYrQaW7piaR5kUjCwtupUZvFwsP6OxbkYoAeQFSl4uIFT3xD03D+PaZKC8XAT/yQxBJzYzo3WE4NoqjnXn7SASBq3NKhIedjjoZLe0DjJbf+jskEM6MsqZ33vP7LwTgRjHPQxeEpzC5GUJuATrllwoY+yADkt0pnQ3YVncHDOZ9JD5eHwJYQasdFE7u7rBtiCwELbhnSqBoISuvJvYKQVYGhytzr/4N+9UpqWmA3jPVY2q/irpEiNdzNvZXVD72bnD7a6KMSprg1WhrUDbk56vA0vM37q/6UxE3X; s_sq=%5B%5BB%5D%5D; s_fid=0E1E85B30079EDB7-2E3D8DBDA6852F62; s_nr=1502251450239-Repeat; s_invisit=true; ubid-main=130-4095001-7074404; session-token="4yhZlamIcYrU1DZfYPvs1BhMs/rdHqX3cwYY+ZQq/1BA0VkLL1S8aOb07GrXq+a6of7SN4G4TU3kXluBLrLA4J42N8gaDvDtzJVFTsTS7U7JK+fuCncVADk5zj7mCeIXOPFFJhGVwjDH+rEa6ylTNaSGWWdwm0TG0HMytp2Xppg2V4dLp5aT9DVykPlNWQXm1RTi4MA4GhfJIz4jT7RHDuvpUsAwomENUTHQrEHKfXA="; x-main="9W63zN9UT1fP7wFFulrQCySiqyHDVCZRROtO4AEadXGqg?aKn8incXurOa?IV70B"; at-main=Atza|IwEBIHnnqJrZUR4M-Ck1rRAajJqg3bi5ISnhORofJZi_U_ZrfblII8LScm5a1FwPF5xvZFHfGB-NHG40DGiLdv0e7B0ZKvySzx8azeixIW3cKIaF1t6gicmHL94iOaIi1ypQjFcvRN016UCdvt_55topq16DxSBl4plbA3MR4I-gm0eursu9jOWsP7v8-WegvsNBSYqF4rd-tRYIZQc0Kb1hKDu7vgLfS2w9irVMuIqJFOVBVOjDB__YyFjys-wEHlzzQLuJS6SIzD2dCLsLTZjZjiQc2gaCiAp1GsCcEKAzUXo2vvwA6oiYPhNg2EDwPsJ7VbMsr2Mzfi0Do9bP-yJ9sjXv-lvS7ABDBvb6MddijwcAYLycEhBLYtI1yDH4PTwVmSKYGsreQ-kImbqGuK5IG5Qa; sess-at-main="bWzIO/RenrqL+mSNeL54fp5P7kRlzR9QtxF3DJtLUrI="'
            cookie = {}
            #output += "<h1>Cookie deconstruction:</h1><br />"
            for pair in raw_cookie.split(";"):
                key_val = pair.split("=")
                key = key_val[0]
                val = key_val[1]
                #output += "<ul>"
                #output += "<li><b>"+key+":</b>"+val+"</li>"
                #output += "</ul>"

                cookie[key] = val


            r = requests.post('https://pitangui.amazon.com/api/cards', cookies=cookie)
            output += "<h1>Website contents:</h1><br />"
            output += "<b>Status code: "+str(r.status_code)+"</b><br /><br />"
            output += "<b>Contents type: "+r.headers['content-type']+"</b><br /><br />"
            output += "<b>Encoding: "+r.encoding+"</b><br /><br />"
            output += "<b>Text: "+r.text+"</b><br /><br />"


        except urllib.error.URLError as e:
            logging.info("Got error!!!")
            logging.info("error_code"+ str(e.code))
            #logging.info("error_reason", e.reason)
            #logging.info("error_message: ", e.read)
            #output += "Error: "+e.reason+"<br />"


    logging.info("Ended amazon login...")
    '''


    return output, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/audio', methods=["GET", "POST"])
def audio_recordings():
    logging.info("Getting the audio recordings...")

    #https://pitangui.amazon.com/api/cards?limit=50&beforeCreationTime=1502236634383
    #https://pitangui.amazon.com//api/utterance/audio/data?id=Rio:1.0/2017/08/08/23/G030K51071751104/08:34::TNIH_2V.09131bbc-e83f-4500-8173-0b5cace04684ZXV/0
    #https://alexa.amazon.com/spa/index.html#cards
    time_str = str(time.time())
    time_str = time_str.replace(".","")
    time_str = time_str[0:-4]
    output = "Timestamp: " + time_str + "\n"

    url_string = 'https://pitangui.amazon.com/api/cards?limit=50&beforeCreationTime='+time_str
    logging.info("URL string: "+url_string)
    output += "URL string: "+url_string+"\n"

    with urllib.request.urlopen(url_string) as response:
        byte_resp = response.read()
        text_resp = byte_resp.decode('utf-8')
        logging.info("Response: " + text_resp)
        output += text_resp
        #card_list = json.loads(json_resp.decode('utf-8'))
        #for key, value in card_list.items():
         #   logging.info("Key: "+str(key) +", Value: "+str(value))


    return output, 200, {'Content-Type': 'text/html; charset=utf-8'}

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
        authorization_token=bot_token
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
    slack_event = json.loads(request.data.decode('utf-8'))
    for key, value in slack_event.items():
        logging.info("Key: "+str(key) +", Value: "+str(value))

    logging.info("After trying to write they json listening stuff...")
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
        # Then handle the event by event_type and have your bot respond
        return _event_handler(event_type, slack_event)
    # If our bot hears things that are not events we've subscribed to,
    # send a quirky but helpful error response
    return make_response("[NO EVENT IN SLACK REQUEST] These are not the droids\
                         you're looking for.", 404, {"X-Slack-No-Retry": 1})

@app.route("/admin", methods=["GET", "POST"])
def admin_view():
    team_approvals = TeamApproval.query.order_by(sqlalchemy.desc(TeamApproval.timestamp)).limit(10)
    survey_question_log = SurveyQuestionLog.query.order_by(sqlalchemy.desc(SurveyQuestionLog.timestamp)).limit(200)
    study_participants = Participant.query.order_by(sqlalchemy.desc(Participant.time_added)).limit(30)

    #get survey schemas
    surveys = Survey.query.order_by(sqlalchemy.asc(Survey.id)).limit(10)
    #get questions for these surveys
    questions = SurveyQuestion.query.order_by(sqlalchemy.asc(SurveyQuestion.id)).limit(30)
    #get survey schedules
    schedules = SurveySchedule.query.order_by(sqlalchemy.asc(SurveySchedule.id)).limit(50)
    #get participant - survey assigment
    surveyAssignments = ParticipantSurveyAssignment.query.order_by(sqlalchemy.asc(ParticipantSurveyAssignment.id)).limit(60)

    return render_template("admin.html", 
        utc_time=utcnow().isoformat(' '),
        pst_time=pstnow().isoformat(' '),
        study_participants=study_participants, 
        team_approvals=team_approvals, 
        survey_question_log=survey_question_log,
        survey_schemas=surveys,
        survey_questions=questions,
        survey_schedules=schedules,
        participant_survey_assignment=surveyAssignments)
    #return output, 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/cronTick')
def cron_tick():
    if "X-Appengine-Cron" in request.headers:
        logging.info("Got CRON request: "+str(request.headers['X-Appengine-Cron']))

    pst_time_now = pstnow()    
    logging.info("Received a cron update tick at" + pst_time_now.isoformat(' '))

    user_ip = request.remote_addr
    logging.info("Got user ip:" + user_ip)

    logging.info("Beginning update of all participants...")
    update_all_users()

    return 'Cron tick at: ' + pst_time_now.isoformat(' '), 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route("/updateAllParticipants", methods=["GET", "POST"])
def update_all_users():
    logging.info("Trying to update all the participants now...")
    users = Participant.query.all()
    n = 1
    for user in users:
        logging.info("Updating participant ["+str(n)+"] id: "+user.id+", name: "+user.name)
        user.update()
        n=n+1
    
    #update the participant in the DB
    db.session.commit()
    logging.info("Update finished!")

    json_enc_question = json.dumps({})
    return make_response(json_enc_question, 200, {"content_type":"application/json"})

@app.route("/setDeviceIDForUser", methods=["GET", "POST"])
def setting_device_id_for_user():
    logging.info("Setting the device id for user...")

    user_id = request.args.get('user_id')
    new_device_id = request.args.get('new_device_id')

    user = Participant.query.filter_by(id=user_id).first()
    if user:
        user.device_id = new_device_id
        db.session.commit()

    json_enc_question = json.dumps({})
    return make_response(json_enc_question, 200, {"content_type":"application/json"})
    
@app.route("/setTaskForUserRQ", methods=["GET", "POST"])
def setting_task_for_user_RQ():
    logging.info("Setting the task for user RQ...")

    user_id = request.args.get('user_id')
    log_id = request.args.get('log_id')
    task = request.args.get('task')

    rqa = ReflectiveQuestionAssignment.query.filter_by(user_id=user_id, id=log_id).first()
    if rqa:
        if task == "None":
            rqa.task = None
        else:
            rqa.task = task

        db.session.commit()

    json_enc_question = json.dumps({})
    return make_response(json_enc_question, 200, {"content_type":"application/json"})

@app.route("/getSlackTeamMembers", methods=["GET", "POST"])
def get_slack_team_members():
    logging.info("Asked for slack team members...")
    team_id = request.args.get('team_id') #request.form['text']
    logging.info("Team id <{}> members".format(team_id))

    logging.info("Size of team bots: " + str(len(team_bots)))
    team_members = []
    if team_id in team_bots:
        logging.info("Found the team_id in team bots")
        team_members = team_bots[team_id].get_users_in_team()

    return render_template("team_members.html", team_id=team_id, team_members=team_members)    

@app.route("/isAudioOnServer", methods=["GET", "POST"])
def is_audio_on_server():
    logging.info("Checking if audio already on server...")
    filepath = request.args.get('filepath')
    logging.info("Filepath: "+filepath)

    audio_recording = {}

    recording = AudioRecordingLog.query.filter_by(audio_url=filepath).first()
    if recording:
        logging.info("Recording on server!")
        audio_recording = {
            "answer": "yes",
            "filepath": filepath
        }
    else:
        logging.info("Recording not on server!")
        audio_recording = {
            "answer": "no",
            "filepath": filepath 
        }

    json_enc_question = json.dumps(audio_recording)
    return make_response(json_enc_question, 200, {"content_type":"application/json"})

@app.route("/addAudioToServer", methods=["GET", "POST"])
def add_audio_to_server():
    logging.info("Adding audio to server...")

    user_id = request.args.get('user_id')
    timestamp = request.args.get('timestamp')
    rqa_id = request.args.get('rqa_id')
    rq_id = request.args.get('rq_id')
    rq_date = request.args.get('rq_date')
    rq_type = request.args.get('rq_type')
    audio_url = request.args.get('audio_url')

    logging.info("Filepath: "+audio_url)

    
    audioRecordingLog = AudioRecordingLog(
                            user_id=user_id,
                            timestamp=timestamp,
                            rqa_id=rqa_id,
                            rq_id=rq_id,
                            rq_date=rq_date,
                            rq_type=rq_type,
                            audio_url=audio_url)

    logging.info("Adding the audio recording to db DB...")
    db.session.add(audioRecordingLog)
    db.session.commit()
    

    audio_recording = {
        "status": "OK"
    }
    json_enc_question = json.dumps(audio_recording)
    return make_response(json_enc_question, 200, {"content_type":"application/json"})


@app.route("/getReflectiveQuestion", methods=["GET", "POST"])
def get_reflective_question():
    logging.info("Asked to generate reflective question...")
    alexa_device_id = request.args.get('device_id') #request.form['text']
    logging.info("A question for device_id: {}".format(alexa_device_id))

    #questions = {
    #    "amzn1.ask.device.AEX5M7GZOVQIO5TWUZS2HQEIY5JTUWL4KEBEXBKBP52QP4C4T4WXBO4M7XDXQHMZUSX7GNRNSIZURSKIKP52YE4QRYV2XKNSUH7BVS4P6HJULBJGX27QOGBBJYV5JBXTYIOOKWBXMLQH4P5JREHEOAQ2ZWUQ": "What did you learn at work today?",
    #    "amzn1.ask.device.AEX5M7GZOVQIO5TWUZS2HQEIY5JU3J57KRJUR5QWHULRUU3LEHNHI6GTNEJM5L2H6VPTNG52ZZ4572YK73XQP6MFXOJTFKTAXZCAAILLZKG6MMHGUA5WD2L5YV553PM4N7TG4DLL7YMPQKB27QU5ZZWKBLGQ": "Why are you still working on reflection? What is the value of that?"
    #}

    json_enc_question = json.dumps({}) # empty response if something went wrong, is handled on the Alexa side now

    #find the user this device belongs to
    logging.info("Trying to find the participant this device belongs to...")
    participant = Participant.query.filter_by(device_id=alexa_device_id).first()
    if participant:
        logging.info("Participant found, id: "+participant.id+", name: "+participant.name)
        question_data = participant.get_reflective_question_for_now()
        if question_data["question_text"]:
            #log that we sent the message
            surveyQuestionLog = SurveyQuestionLog(
                                    user_id=participant.id,
                                    survey_log_id=None,
                                    survey_id=None,
                                    schedule_id=None,
                                    question_id=None,
                                    question_type="VOICE_QUESTION_RETRIEVAL",
                                    text=question_data["question_text"])

            logging.info("Logging survey question retrieved by voice to DB...")
            db.session.add(surveyQuestionLog)
            db.session.commit()

            json_enc_question = json.dumps({
                'user_id': participant.id, 
                'name': participant.name,
                "rq_id": question_data["question_id"],
                "rq_assignment_id": question_data["question_assignment_id"], 
                "rq_date": question_data["question_date"].strftime("%Y-%m-%d"),
                'rq_text': question_data["question_text"]})
        else:
            logging.warning("No question can be found for participant id: "+participant.id+", name: "+participant.name+" for date: "+question_data["question_date"].isoformat(' '))
    else:
        logging.warning("No participant can be found assigned to this device!")

    #if alexa_device_id in questions:
    #    json_enc_question = json.dumps({'name': name, 'question_text': questions[alexa_device_id]})
    
    return make_response(json_enc_question, 200, {"content_type":"application/json"})

@app.route("/setReflectionResponse", methods=["GET", "POST"])
def log_reflection_response():
    logging.info("Asked to log reflection response...")
    alexa_device_id = request.args.get('device_id') #request.form['text']
    reflection_text = request.args.get('text')
    is_followup = request.args.get('is_followup')

    thank_you_text = "Your reflection has been recorded. Thank you and have a great day!"

    logging.info("Got a reflection response from Alexa text:{}, device_id:{}, is_followup:{}".format(reflection_text, alexa_device_id, is_followup))
    logging.info("Find the user this reflection response belongs to...")

    json_enc_question = json.dumps({}) # empty response if something went wrong, is handled on the Alexa side now

    user = Participant.query.filter_by(device_id=alexa_device_id).first()
    if user:
        #determine the type of the question answered
        logging.info("Determine whether it is original or follow-up: "+is_followup)
        question_type="USER_VOICE_MESSAGE"
        if is_followup == "True":
            logging.info("It is just a follow-up, don't thank again!")
            question_type="USER_VOICE_FOLLOWUP"

            #user.send_dm_message("Hey, thanks for your reflection, you shared with us: "+reflection_text)
            logging.info("User id: "+user.id+" and name: "+user.name+" found and question assigned!")
            sql2 = SurveyQuestionLog(
                    user_id=user.id,
                    survey_log_id=None,
                    survey_id=None,
                    schedule_id=None,
                    question_id=None,
                    question_type=question_type,
                    text=reflection_text)

            logging.info("Logging reflection response received to DB...")
            db.session.add(sql2)
            db.session.commit()

        else:
            logging.info("Original response, say thank you on Slack!")
            user.send_dm_message(thank_you_text)

            #check if there is open reflection survey that has been initated by the system that we are closing
            create_survey = True
            open_survey_log_id = None
            open_survey_id = None
            open_survey_schedule_id = None
            open_survey_question_id = None
            logging.info("Check if this is in response to an open reflection survey by the system, or user initiated...")
            sls = SurveyLog.query.filter_by(user_id=user.id, time_closed=None).limit(10)
            if sls.count() > 1:
                logging.warning("We have have a problem, "+str(sls.count()) +" surveys were open in logging reflection response, that is strange, because if we are in open work survey, we should have only one opene still!")
            if sls.count() > 0:
               logging.info("We have one open survey when receiving reflective response, that't as expected with system initiated reflection, but we can also be in work reporting survey, we need to check!")

            #log that the survey has been completed
            for sl in sls:
                logging.info("Checking survey log: "+str(sl.id)+", survey_id:"+str(sl.survey_id)+" for user: "+sl.user_id+", opened on: "+sl.time_started.isoformat(' '))
                open_survey = Survey.query.get(sl.survey_id)
                if open_survey:
                    if open_survey.type == "REFLECTION" and open_survey.modality == "WAND":
                        create_survey = False
                        open_survey_log_id = sl.id
                        open_survey_id = open_survey.id
                        open_survey_schedule_id = sl.schedule_id
                        break

            if create_survey == False:
                logging.info("We are just closing a system initiated reflection survey, no need to create anything")
                if user.state.startswith("SURVEY_QUESTION_ASKED"):
                    logging.info("We are in survey question asking state")
                    #determine survey id and question id
                    ids = Participant.extract_ids_from_survey_question_state(user.state)
                    if "survey_id" in ids and "question_id" in ids and "schedule_id" in ids:
                        survey_id = ids['survey_id']
                        question_id = ids['question_id']
                        schedule_id = ids['schedule_id']
                        open_survey_question_id = question_id

                #user.send_dm_message("Hey, thanks for your reflection, you shared with us: "+reflection_text)
                logging.info("User id: "+user.id+" and name: "+user.name+" found and question assigned!")
                sql2 = SurveyQuestionLog(
                        user_id=user.id,
                        survey_log_id=open_survey_log_id,
                        survey_id=open_survey_id,
                        schedule_id=open_survey_schedule_id,
                        question_id=open_survey_question_id,
                        question_type=question_type,
                        text=reflection_text)

                logging.info("Logging reflection response received to DB...")
                db.session.add(sql2)
                db.session.commit()

                user.update()
            else:
                logging.info("It is user initiated reflection, we need to create the whole survey log!")

                #log the whole reflection survey
                created = False
                pas_assignments = ParticipantSurveyAssignment.query.filter_by(user_id=user.id).limit(10)
                for pas in pas_assignments:
                    if created == True:
                        logging.info("We already created it not need to check other survey assignments!")
                        break

                    survey = Survey.query.filter_by(id=pas.survey_id).first()
                    if survey:
                        if survey.type == "REFLECTION" and survey.modality == "WAND":
                            logging.info("Found wand reflection survey: "+str(survey.id)+", name:"+survey.name+"!")
                            logging.info("Checking it's schedule")
                            survey_schedule = SurveySchedule.query.filter_by(survey_id=survey.id).limit(10)

                            now = pstnow()
                            today_week_day = now.weekday()

                            for schedule_entry in survey_schedule:
                                logging.info("Schedule entry ["+str(schedule_entry.id)+"] -> week_day: "+str(schedule_entry.week_day))
                                if schedule_entry.week_day == today_week_day:
                                    # Adding the entry to survey_log
                                    sl = SurveyLog(
                                        user_id=user.id,
                                        survey_id=survey.id,
                                        schedule_id=schedule_entry.id
                                    )
                                    sl.time_started = now - timedelta(seconds=30)

                                    logging.info("Trying to add survey started log: "+str(survey.id)+", schedule id:"+str(schedule_entry.id)+" for user: "+str(user.id)+" to DB...")
                                    db.session.add(sl)
                                    db.session.flush()
                                    db.session.refresh(sl)

                                    sq_id = None
                                    sq = SurveyQuestion.query.filter_by(survey_id=survey.id).order_by(sqlalchemy.asc(SurveyQuestion.id)).first()
                                    if sq:
                                        sq_id = sq.id

                                    question_data = user.get_reflective_question_for_now()
                                    sql1 = SurveyQuestionLog(
                                            user_id=user.id,
                                            survey_log_id=sl.id,
                                            survey_id=survey.id,
                                            schedule_id=schedule_entry.id,
                                            question_id=sq_id,
                                            question_type="SURVEY_QUESTION",
                                            text=question_data["question_text"])

                                    logging.info("Logging survey question sent to DB...")
                                    db.session.add(sql1)

                                    #user.send_dm_message("Hey, thanks for your reflection, you shared with us: "+reflection_text)
                                    logging.info("User id: "+user.id+" and name: "+user.name+" found and question assigned!")
                                    sql2 = SurveyQuestionLog(
                                        user_id=user.id,
                                        survey_log_id=sl.id,
                                        survey_id=survey.id,
                                        schedule_id=schedule_entry.id,
                                        question_id=sq_id,
                                        question_type=question_type,
                                        text=reflection_text)

                                    logging.info("Logging reflection response received to DB...")
                                    sql2.timestamp = now - timedelta(seconds=10)
                                    db.session.add(sql2)

                                    #close the survey_log
                                    sl.time_completed = now
                                    sl.time_closed = now

                                    db.session.commit()
                                    created = True
                                    logging.info("Reflection survey entry done!")
                                    break
    

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
def update_participant():
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

@app.route("/assignReflectiveQuestionsToParticipant", methods=["GET", "POST"])
def assign_reflective_questions_to_participant():
    logging.info("Assigning reflective questions to participant...")
    user_id = request.args.get('user_id') #request.form['text']
    logging.info("User id <{}>".format(user_id))

    if user_id:
        rq_ids = []
        #get the list of reflective questions we have available
        reflective_questions = ReflectiveQuestion.query.limit(30)
        logging.info("Got some "+str(reflective_questions.count())+" reflective questions to assign...")
        for rq in reflective_questions:
            rq_ids.append(rq.id)

        #Randomly select reflective questions by id without repetition
        assigned_ids = []
        logging.info("Randomly scrambling the questions ids...")
        while len(rq_ids) > 0:
            sel_id = randrange(0,len(rq_ids))
            logging.info("Selected list temp id: "+str(sel_id) + " corresponding RQ id: " + str(rq_ids[sel_id]))
            assigned_ids.append(rq_ids[sel_id])
            del rq_ids[sel_id]

        logging.info("The rendomly scrambled questions ids we have: "+str(assigned_ids))

        #Assign to the actual dates
        day = 0
        pst_now = pstnow()
        act_date = generate_pacific_date(pst_now.year, pst_now.month, pst_now.day,0,0,0)

        logging.info("Assigning question ids to dates...")
        while len(assigned_ids) > 0:
            
            logging.info("Checking if date: "+act_date.isoformat(' ')+" is weekday ...")
            weekday = act_date.weekday()
            logging.info("Day of week is: "+str(weekday))

            if weekday < 5:
                logging.info("It is week day, assigning question id: "+str(assigned_ids[0])+ " to date: "+act_date.isoformat(' '))
                #get existing entry for this data if there is such
                rq_entry = ReflectiveQuestionAssignment.query.filter(ReflectiveQuestionAssignment.date == act_date).filter_by(user_id=user_id).first()
                
                if rq_entry:
                    logging.info("Already has reflective question for date: "+act_date.isoformat(' ')+", changing...")
                    rq_entry.question_id = assigned_ids[0]

                    db.session.commit()

                else:
                    logging.info("No reflective question assigned for date: "+act_date.isoformat(' ')+", assigning...")
                    rqa = ReflectiveQuestionAssignment(
                        user_id=user_id,
                        question_id=assigned_ids[0],
                        date=act_date
                    )

                    logging.info("Trying to add reflective question assignment id: "+str(assigned_ids[0])+" for user: "+str(user_id)+" to DB...")
                    db.session.add(rqa)
                    db.session.commit()

                del assigned_ids[0]
            else:
                logging.info("Not a weekday, skipping")

            act_date = act_date + timedelta(days=1)

    else:
        logging.warning("User id is empty when running assign_reflective_questions_to_participant!")

    return make_response("{}", 200, {"content_type":"application/json"})

@app.route("/getRQsForParticipant", methods=["GET", "POST"])
def get_assigned_reflective_questions_for_participant():
    logging.info("Asked for a list of assigned reflective questions...")
    user_id = request.args.get('user_id') #request.form['text']
    logging.info("User id <{}>".format(user_id))

    reflective_questions = []
    #get question assignment for this user
    question_assignments = ReflectiveQuestionAssignment.query.filter_by(user_id=user_id).order_by(sqlalchemy.asc(ReflectiveQuestionAssignment.date)).limit(30)
    for aq in question_assignments:
        rq = ReflectiveQuestion.query.filter_by(id=aq.question_id).first()
        if rq:
            #pst_now = pstnow()
            #date_portion = generate_pacific_date(pst_now.year, pst_now.month, pst_now.day, 0, 0, 0)
            #logging.info("Date for finding the reflective question: "+date_portion.isoformat(' '))
            question_text = rq.text
            participant = Participant.query.get(user_id)
            if participant:
                question_text = participant.construct_reflective_question_for_date(aq.date)

            reflective_questions.append({   "id": aq.id, 
                                            "date": aq.date, 
                                            "question_id": aq.question_id,
                                            "text": rq.text.replace("<task>","<span class='tmpl_field'>task</span>").replace("<completed>","<span class='tmpl_field'>n_completed</span>").replace("<progress>","<span class='tmpl_field'>n_progress</span>").replace("<planned>","<span class='tmpl_field'>n_planned</span>"),
                                            "type": rq.type,
                                            "task": aq.task,
                                            "n_completed": aq.n_completed,
                                            "n_progress": aq.n_progress,
                                            "n_planned": aq.n_planned,
                                            "final_text": question_text
                                             })

    return render_template("reflective_question_assignment.html", user_id=user_id, reflective_questions=reflective_questions)    

@app.route("/getSurveyLogForParticipant", methods=["GET", "POST"])
def get_survey_log_for_participant():
    logging.info("Asked for survey log...")
    user_id = request.args.get('user_id') #request.form['text']
    logging.info("User id <{}>".format(user_id))

    survey_logs = []
    #get question assignment for this user
    sl = SurveyLog.query.filter_by(user_id=user_id).order_by(sqlalchemy.desc(SurveyLog.time_started)).limit(40)
    rmdrs = SurveyReminderLog.query.filter_by(user_id=user_id).order_by(sqlalchemy.desc(SurveyReminderLog.timestamp)).limit(200)
    return render_template("survey_log.html", user_id=user_id, survey_log=sl, survey_reminders=rmdrs)    

@app.errorhandler(500)
def server_error(e):
    logging.exception('An error occurred during a request.')
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500

if __name__ == '__main__':
    app.run(debug=True)
