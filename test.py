

import datetime

from dataMgr import db

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

'''

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



