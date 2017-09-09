

import datetime
import pytz

from datetime import datetime, timedelta
from pytz import timezone
from pytz import common_timezones
from pytz import country_timezones

import random
from random import random, randrange
import dataMgr
from dataMgr import db
from dataMgr import SurveyQuestionLog
import sqlalchemy

def utcnow():
	return datetime.now(tz=pytz.utc)

def pstnow():
	utc_time = utcnow()
	pacific = timezone('US/Pacific')
	pst_time = utc_time.astimezone(pacific)
	return pst_time

#def generate_pacific_date(year, month, day, hour, minute, second):
#	pacific = timezone('US/Pacific')
#	dt = datetime(year, month, day, 15, 37, 0)
#	in_pacific = pacific.localize(dt, is_dst=True)
#	return in_pacific

def generate_pacific_date(year, month, day, hour, minute, second):
	pacific = timezone('US/Pacific')
	dt = datetime(year, month, day, hour, minute, second)
	in_pacific = pacific.localize(dt, is_dst=True)
	return in_pacific

class Test(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	number = db.Column(db.Integer)
	date = db.Column(db.DateTime())

	bot_ref = None

	def __init__(self, id, number):
		print("Constructor")
		self.number = number
		self.date = datetime.datetime.now()

		self.bot_ref = None

	def set_bot_ref(self, bot_ref):
		self.bot_ref = bot_ref

	def get_bot_ref(self):
		return self.bot_ref


print("Testing")
#pacific = timezone('US/Pacific')
#utc_time = utcnow()
print("UTC time:" + utcnow().isoformat(' '))
#pacific_time = utc_time.astimezone(pacific)
print("Pacific time:" + pstnow().isoformat(' '))

#2017-08-06 21:06:28-07:00
qtime = generate_pacific_date(2017, 8, 6, 23, 37, 50)
print("Cut off date from question: " + qtime.isoformat(' '))


sql_answers = SurveyQuestionLog.query.filter(SurveyQuestionLog.timestamp>qtime).order_by(sqlalchemy.desc(SurveyQuestionLog.timestamp)).limit(20)
if sql_answers:
	print("Got "+str(sql_answers.count())+" answers...")
	n = 1
	for ans in sql_answers:
		print("Got answer ["+str(n)+"]: "+ans.timestamp.isoformat(' ')+", text: "+ans.text)
		n=n+1

'''
n=0
print("# of common timezones: ", len(common_timezones))
for tz in common_timezones:
	print("Zone:["+tz+"]")
	n=n+1
	if (n>10):
		break

n=0
print("# of country timezones: ", len(country_timezones))
for tz in country_timezones:
	print("Zone:["+tz+"]")
	n=n+1
	if (n>10):
		break


print("US timezones: ")
for tz_us in country_timezones['us']:
	print("US zone:"+tz_us)

end_day_time = datetime(pstnow().year, pstnow().month, pstnow().day, 23, 30, tzinfo=pytz.utc)
print("End day in UTC: "+end_day_time.isoformat(' '))
pacific = timezone('US/Pacific')
#end_day_time2 = datetime(2017, 7, 28, 14, 30, 0, 0, tzinfo=pacific)
dt = datetime(pstnow().year, pstnow().month, pstnow().day, 15, 37, 0)
end_day_time2 = pacific.localize(dt, is_dst=True)


print("End day in PST: "+end_day_time2.isoformat(' '))


print("Pacific time:" + pstnow().isoformat(' '))
if pstnow()>end_day_time2:
	print("Day ended in PST!")
else:
	print("Day did not end in PST!")


ids = [1,2,3,4,5,6,7,8,9,10]
assigned = []
print("Length of list: " + str(len(ids)))
while len(ids) > 0:
	sel_id = randrange(0,len(ids))
	print("Sel id: "+ str(sel_id) + ", value: "+str(ids[sel_id]))
	assigned.append(ids[sel_id])
	#ids.remove(sel_id)
	del ids[sel_id]
	print("List is: ", ids)

print("Assigned: ", assigned )
'''


'''
db.create_all()

test = Test(1, 8)
test2 = Test(2, 67)
test3 = Test(3, 190)
test4 = Test(4, 67)

db.session.add(test)
#db.session.add(test2)
#db.session.add(test3)
#db.session.add(test4)
db.session.commit()

now = datetime.datetime.now()
print("Now date is: "+now.isoformat(' '))
mydate = datetime.datetime(now.year, now.month, 27, 2, 7,0 )
print("My date is: "+mydate.isoformat(' '))

results = Test.query.filter(Test.date>=mydate).limit(10)
print("Got "+str(results.count())+" results...")
n=1
for r in results:
	print("Result ["+str(n)+"]: "+str(r.number)+", date: "+r.date.isoformat(' '))
	n=n+1

print("Listing the team....")
test_list = Test.query.limit(20)
n = 1
for test in test_list:
	print("Test ["+str(n)+"] -> "+str(test.get_bot_ref()))
	test.set_bot_ref(12*n)
	print("Test ["+str(n)+"] -> "+str(test.get_bot_ref()))

	n=n+1

print("Listing afterwards team....")
test_list = Test.query.limit(20)
n = 1
for test in test_list:
	print("Test ["+str(n)+"] -> "+str(test.get_bot_ref()))

	n=n+1

print("DATE TIME TESTING")
now = datetime.datetime.now()
print("The time now is: "+now.isoformat(' '))

today_23_30 = datetime.datetime(now.year, now.month, now.day, 13, 30)
print("COmparison time is: "+today_23_30.isoformat(' '))

if now > today_23_30:
	print("Time to send!")

state ={}
state[0] = "SURVEY_QUESTION_ASKED_1_1"
state[1] = "SURVEY_QUESTION_ASKED_1_2"
state[2] = "SURVEY_QUESTION_ASKED_2_1"
state[3] = "REFLECTION_QUESTION_ASKED"
 
for s in state:
	print("State matches? " + str( state[s].startswith("SURVEY_QUESTION_ASKED") ) )
'''