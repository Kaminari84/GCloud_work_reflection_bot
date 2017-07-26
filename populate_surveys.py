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


if __name__ == '__main__':
	print('Creating all database tables...')
	db.create_all()
	print('Done!')


	print('Populating surveys and questions...')

	s1 = Survey(id=1, name="Morning survey")
	q1_1 = SurveyQuestion(id=1, survey_id=1, text="What have you accomplished yesterday?")
	q1_2 = SurveyQuestion(id=2, survey_id=1, text="What are you planning to do tomorrow?")
	s1_day1 = SurveySchedule(id=1, survey_id=1, week_day=0, hour=10, minute=0)
	s1_day2 = SurveySchedule(id=2, survey_id=1, week_day=1, hour=10, minute=0)

	s2 = Survey(id=2, name="Mid-day survey")
	q2_1 = SurveyQuestion(id=21, survey_id=2, text="What have you accomplished earlier in the day?")
	q2_2 = SurveyQuestion(id=22, survey_id=2, text="What are you planning to do for the rest of the day?")
	s2_day1 = SurveySchedule(id=3, survey_id=2, week_day=2, hour=13, minute=0)
	s2_day2 = SurveySchedule(id=4, survey_id=2, week_day=3, hour=13, minute=0)

	s3 = Survey(id=3, name="Afternoon survey")
	q3_1 = SurveyQuestion(id=31, survey_id=3, text="What have you accomplished today?")
	q3_2 = SurveyQuestion(id=32, survey_id=3, text="What are you planning to do tomorrow?")
	s3_day1 = SurveySchedule(id=5, survey_id=3, week_day=4, hour=16, minute=0)
	s3_day2 = SurveySchedule(id=6, survey_id=3, week_day=5, hour=16, minute=0)

	print("Trying to add survey data to DB...")
	
	db.session.merge(s1)
	db.session.merge(q1_1)
	db.session.merge(q1_2)
	db.session.merge(s1_day1)
	db.session.merge(s1_day2)
	
	db.session.merge(s2)
	db.session.merge(q2_1)
	db.session.merge(q2_2)
	db.session.merge(s2_day1)
	db.session.merge(s2_day2)

	db.session.merge(s3)
	db.session.merge(q3_1)
	db.session.merge(q3_2)
	db.session.merge(s3_day1)
	db.session.merge(s3_day2)
	
	db.session.commit()


	print('Done!')
# [END all]