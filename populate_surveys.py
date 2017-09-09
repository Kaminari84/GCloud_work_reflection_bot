#! /usr/bin/env python
# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START all]

from dataMgr import db
from dataMgr import SurveyQuestion
from dataMgr import Survey
from dataMgr import SurveySchedule
from dataMgr import ReflectiveQuestion


if __name__ == '__main__':
	print('Creating all database tables...')
	db.create_all()
	print('Done!')


	print('Populating surveys and questions...')

	# MORNING SURVEY #
	s1 = Survey(id=1, name="Morning survey", type="REPORT", modality="SLACK", 
		start_text="Hey <name>, it is time for your activity report today!",
		end_text="Thanks for completing your activity report!")
	q1_1 = SurveyQuestion(id=1, survey_id=1, text="What have you accomplished yesterday?")
	q1_2 = SurveyQuestion(id=2, survey_id=1, text="What are you planning to do today?")
	s1_day1 = SurveySchedule(id=1, survey_id=1, week_day=0, hour=9, minute=58)
	s1_day2 = SurveySchedule(id=2, survey_id=1, week_day=1, hour=9, minute=58)
	s1_day3 = SurveySchedule(id=3, survey_id=1, week_day=2, hour=9, minute=58)
	s1_day4 = SurveySchedule(id=4, survey_id=1, week_day=3, hour=9, minute=58)
	s1_day5 = SurveySchedule(id=5, survey_id=1, week_day=4, hour=9, minute=58)

	#s1_day7 = SurveySchedule(id=6, survey_id=1, week_day=6, hour=9, minute=58)


	db.session.merge(s1)
	db.session.merge(q1_1)
	db.session.merge(q1_2)
	db.session.merge(s1_day1)
	db.session.merge(s1_day2)
	db.session.merge(s1_day3)
	db.session.merge(s1_day4)
	db.session.merge(s1_day5)
	#db.session.merge(s1_day7)

	# MID-DAY SURVEY #
	s2 = Survey(id=2, name="Mid-day survey", type="REPORT", modality="SLACK", 
		start_text="Hey <name>, it is time for your activity report today!",
		end_text="Thanks for completing your activity report!")
	q2_1 = SurveyQuestion(id=21, survey_id=2, text="What have you accomplished earlier in the day?")
	q2_2 = SurveyQuestion(id=22, survey_id=2, text="What are you planning to do for the rest of the day?")
	s2_day1 = SurveySchedule(id=11, survey_id=2, week_day=0, hour=13, minute=28)
	s2_day2 = SurveySchedule(id=12, survey_id=2, week_day=1, hour=13, minute=28)
	s2_day3 = SurveySchedule(id=13, survey_id=2, week_day=2, hour=13, minute=28)
	s2_day4 = SurveySchedule(id=14, survey_id=2, week_day=3, hour=13, minute=28)
	s2_day5 = SurveySchedule(id=15, survey_id=2, week_day=4, hour=13, minute=28)

	#s2_day7 = SurveySchedule(id=16, survey_id=2, week_day=6, hour=13, minute=28)

	db.session.merge(s2)
	db.session.merge(q2_1)
	db.session.merge(q2_2)
	db.session.merge(s2_day1)
	db.session.merge(s2_day2)
	db.session.merge(s2_day3)
	db.session.merge(s2_day4)
	db.session.merge(s2_day5)

	#db.session.merge(s2_day7)

	# END DAY SURVEY #
	s3 = Survey(id=3, name="Afternoon survey", type="REPORT" , modality="SLACK", 
		start_text="Hey <name>, it is time for your activity report today!",
		end_text="Thanks for completing your activity report!")
	q3_1 = SurveyQuestion(id=31, survey_id=3, text="What have you accomplished today?")
	q3_2 = SurveyQuestion(id=32, survey_id=3, text="What are you planning to do tomorrow?")
	s3_day1 = SurveySchedule(id=21, survey_id=3, week_day=0, hour=15, minute=58)
	s3_day2 = SurveySchedule(id=22, survey_id=3, week_day=1, hour=15, minute=58)
	s3_day3 = SurveySchedule(id=23, survey_id=3, week_day=2, hour=15, minute=58)
	s3_day4 = SurveySchedule(id=24, survey_id=3, week_day=3, hour=15, minute=58)
	s3_day5 = SurveySchedule(id=25, survey_id=3, week_day=4, hour=15, minute=58)

	#s3_day7 = SurveySchedule(id=26, survey_id=3, week_day=6, hour=15, minute=58)
	
	db.session.merge(s3)
	db.session.merge(q3_1)
	db.session.merge(q3_2)
	db.session.merge(s3_day1)
	db.session.merge(s3_day2)
	db.session.merge(s3_day3)
	db.session.merge(s3_day4)
	db.session.merge(s3_day5)

	#db.session.merge(s3_day7)

	# REFLECTION SURVEY ON SLACK #
	s_ref_slack = Survey(id=89, name="Reflection survey - Slack", type="REFLECTION", modality="SLACK", 
		start_text="Hey <name>, it's time for your reflective question!",
		end_text="Your reflection has been recorded. Thank you and have a great day!")
	#s_ref_0 = SurveyQuestion(id=990, survey_id=99, text="Hey, it is time for your daily reflection. Please ") #Introduction question
	s_ref_slack_1 = SurveyQuestion(id=899, survey_id=89, text="REFLECTIVE_QUESTION")
	s_ref_slack_day1 = SurveySchedule(id=80, survey_id=89, week_day=0, hour=16, minute=28)
	s_ref_slack_day2 = SurveySchedule(id=81, survey_id=89, week_day=1, hour=16, minute=28)
	s_ref_slack_day3 = SurveySchedule(id=82, survey_id=89, week_day=2, hour=16, minute=28)
	s_ref_slack_day4 = SurveySchedule(id=83, survey_id=89, week_day=3, hour=16, minute=28)
	s_ref_slack_day5 = SurveySchedule(id=84, survey_id=89, week_day=4, hour=16, minute=28)

	#s_ref_slack_day7 = SurveySchedule(id=85, survey_id=89, week_day=6, hour=16, minute=15)

	db.session.merge(s_ref_slack)
	#db.session.merge(s_ref_slack_0)
	db.session.merge(s_ref_slack_1)
	db.session.merge(s_ref_slack_day1)
	db.session.merge(s_ref_slack_day2)
	db.session.merge(s_ref_slack_day3)
	db.session.merge(s_ref_slack_day4)
	db.session.merge(s_ref_slack_day5)

	#db.session.merge(s_ref_slack_day7)

	# REFLECTION SURVEY ON AKEXA WAND #
	s_ref_wand = Survey(id=99, name="Reflection survey - Wand", type="REFLECTION", modality="WAND", 
		start_text="Hey <name>, it's time for your reflective question. Please press the button on your Amazon Wand and say \"start work reflection\".",
		end_text="Your reflection has been recorded. Thank you and have a great day!")
	#s_ref_0 = SurveyQuestion(id=990, survey_id=99, text="Hey, it is time for your daily reflection. Please ") #Introduction question
	s_ref_wand_1 = SurveyQuestion(id=999, survey_id=99, text="REFLECTIVE_QUESTION")
	s_ref_wand_day1 = SurveySchedule(id=90, survey_id=99, week_day=0, hour=16, minute=28)
	s_ref_wand_day2 = SurveySchedule(id=91, survey_id=99, week_day=1, hour=16, minute=28)
	s_ref_wand_day3 = SurveySchedule(id=92, survey_id=99, week_day=2, hour=16, minute=28)
	s_ref_wand_day4 = SurveySchedule(id=93, survey_id=99, week_day=3, hour=16, minute=28)
	s_ref_wand_day5 = SurveySchedule(id=94, survey_id=99, week_day=4, hour=16, minute=28)

	#s_ref_wand_day7 = SurveySchedule(id=95, survey_id=99, week_day=6, hour=16, minute=28)

	db.session.merge(s_ref_wand)
	#db.session.merge(s_ref_wand_0)
	db.session.merge(s_ref_wand_1)
	db.session.merge(s_ref_wand_day1)
	db.session.merge(s_ref_wand_day2)
	db.session.merge(s_ref_wand_day3)
	db.session.merge(s_ref_wand_day4)
	db.session.merge(s_ref_wand_day5)

	#db.session.merge(s_ref_wand_day7)

	# CREATE ALL THE REFLECTIVE QUESTIONS TO BE USED #
	rq_1 = ReflectiveQuestion(id=1, survey_id=99, text="Thinking about <task> you worked on. What was important for you about this task?", type="TASK")
	rq_2 = ReflectiveQuestion(id=2, survey_id=99, text="Do you feel the activities you did today contributed to your goals? Why or why not?", type="NONE")
	rq_3 = ReflectiveQuestion(id=3, survey_id=99, text="Was there anything that made you happy/unhappy when working on <task>? What was it? How can you learn from it?", type="TASK")
	rq_4 = ReflectiveQuestion(id=4, survey_id=99, text="What were some of the most satisfying moments at work for you this week and why?", type="NONE")
	rq_5 = ReflectiveQuestion(id=5, survey_id=99, text="How do you feel about your performance today? What do you think affected it the most?", type="NONE")

	rq_6 = ReflectiveQuestion(id=6, survey_id=99, text="What helped you and what impeded your progress towards your goals today?", type="NONE")
	rq_7 = ReflectiveQuestion(id=7, survey_id=99, text="How satisfied are you with how you organized your work today? Is there anything you have learned?", type="NONE")
	rq_8 = ReflectiveQuestion(id=8, survey_id=99, text="Did <task> help you learn anything new that could be valuable for the future? What did you learn?", type="TASK")
	rq_9 = ReflectiveQuestion(id=9, survey_id=99, text="How did you organize your work this week? Was it effective?", type="NONE")
	rq_10 = ReflectiveQuestion(id=10, survey_id=99, text="Is having weekly goals useful for you? Why or why not?", type="NONE")

	db.session.merge(rq_1)
	db.session.merge(rq_2)
	db.session.merge(rq_3)
	db.session.merge(rq_4)
	db.session.merge(rq_5)

	db.session.merge(rq_6)
	db.session.merge(rq_7)
	db.session.merge(rq_8)
	db.session.merge(rq_9)
	db.session.merge(rq_10)
	
	print("Trying to add survey data to DB...")

	db.session.commit()

	print('Done!')
# [END all]