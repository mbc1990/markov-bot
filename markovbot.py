import os
import random
import time
import requests
from slackclient import SlackClient
from slacker import Slacker
from collections import defaultdict

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine

Base = declarative_base()

class User(Base):
    __tablename__ = "user"
 
    id = Column(Integer, primary_key=True)
    username = Column(String)
    slack_user_id = Column(String)

    MAX_GEN_LEN = 10
 
    def __init__(self, username, slack_user_id):
        """"""
        self.username = username
        self.slack_user_id = slack_user_id
    
    def add_message(self, message, session):
        print "Adding message: "+message
        lower = message.lower()
        spl = lower.split(' ')
        for i in range(0, len(spl)-1):
            word_a = spl[i]
            word_b = spl[i+1]

            # TODO: Don't do these queries in a loop
            exists = session.query(Bigram).filter(Bigram.word_a==word_a, Bigram.word_b==word_b, Bigram.user_id==self.id)
            if exists.count():
                bg = exists.first()
                bg.count = bg.count+1 
            else:
                bg = Bigram(self.id, word_a, word_b, 1)
            session.add(bg)
            session.commit()

    def generate_message(self, session):
        # Build the map out of saved bigrams
        word_map = defaultdict(list) 
        bigrams = session.query(Bigram).filter(Bigram.user_id==self.id)
        for bg in bigrams:
            key = bg.word_a
            following = bg.word_b
            for i in range(0,bg.count):
                word_map[key].append(following)
            
        # Pick a starting word
        start = random.choice(word_map.keys())
        generated = [start]

        # TODO: Sentence start/end tokens 
        while start in word_map.keys() and len(generated) < self.MAX_GEN_LEN:
            next_word = random.choice(word_map[start])
            generated.append(next_word)
            start = next_word
        
        return ' '.join(generated)

# sqlalchemy models
class Bigram(Base):
    """"""
    __tablename__ = "bigram"
 
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, primary_key=False)
    word_a = Column(String)
    word_b = Column(String)
    count = Column(Integer)
 
    def __init__(self, user_id, word_a, word_b, initial_count):
        """"""
        self.user_id = user_id 
        self.word_a = word_a 
        self.word_b = word_b 
        self.count = initial_count

class MarkovBot():
    DB_NAME = 'markovbot.db'
    BOT_ID = os.environ.get("BOT_ID")
    AT_BOT = "<@" + BOT_ID + ">"
    
    def __init__(self):
        
        # TODO: Connect to slack

        if not os.path.exists(self.DB_NAME):
            print "initializing db"
            self.init_db()

        self.connect_db()
        self.connect_slack()
        # create user

        '''
        user = User("testuser")
        self.session.add(user)
        self.session.commit()
        '''

        # print users
        '''
        users = self.session.query(User).filter(User.username=="testuser")
        for u in users:
            print "User: "+u.username
            print u.generate_message(self.session)
            #u.add_message("this is a test message", self.session)
        '''
        
        # print all bigrams
        '''
        bigrams = self.session.query(Bigram)
        print "printing "+str(bigrams.count())+" bigrams"
        for b in bigrams:
            print b.word_a+' '+b.word_b+' '+str(b.count)
        '''
        # TODO: Initialize markov models for all users    
    
    def create_user(self, user_id):
        print "Creating user for "+str(user_id)
        response = self.slack.users.list()
        users = response.body['members']
        for u in users:
            if u['id'] == user_id:
                user = User(u['name'], user_id)
                self.session.add(user)
                self.session.commit()
                return user
                                
    def parse_slack_output(self, slack_rtm_output):
        output_list = slack_rtm_output
        print output_list
        if output_list and len(output_list) > 0:
            for output in output_list:
                if output and 'text' in output:
                    text = output['text']
                    print "Text: "+text

                    # Don't model yourself 
                    if self.BOT_ID == output['user']:
                        return

                    if self.AT_BOT in text:
                        print "responding..."
                        parsed = text.split(' ')
                        if len(parsed) == 2:
                            uname = parsed[1]
                            print "parsed name: "+uname
                            user = self.session.query(User).filter(User.username==uname)
                            if user.count():
                                print "Generating text..."
                                user = user.one()
                                gen = user.generate_message(self.session)        
                                self.slack_client.api_call("chat.postMessage", channel=output['channel'], text=gen, as_user=True)
                        else:
                            pass
                            # TODO: Error handling?
                    else:
                        userid = output['user']
                        user = self.session.query(User).filter(User.slack_user_id==userid)
                        if not user.count():
                            user = self.create_user(userid)
                        else:
                            user = user.one()
                        user.add_message(text, self.session)

    def init_db(self):
        print "Creating database"
        engine = create_engine('sqlite:///'+self.DB_NAME, echo=False)
        Base.metadata.create_all(engine)

    def connect_db(self):
        print "Connecting to database"
        engine = create_engine('sqlite:///'+self.DB_NAME, echo=False)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def connect_slack(self):
        
        # Connect to regular API
        self.slack = Slacker(os.environ.get('SLACK_BOT_TOKEN'))
        
        # Connect to real time API
        bot_id = os.environ.get("BOT_ID")
        self.slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
        READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
        if self.slack_client.rtm_connect():
            print("MarkovBot connected and running!")
            while True:
                self.parse_slack_output(self.slack_client.rtm_read())
                time.sleep(READ_WEBSOCKET_DELAY)
        else:
            print("Connection failed. Invalid Slack token or bot ID?")


def main():
    MarkovBot()    

if __name__ == "__main__":
    main()
