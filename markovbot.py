import os
import random
import time
import requests
from collections import defaultdict

from slackclient import SlackClient
from slacker import Slacker
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
from nltk.tokenize import TweetTokenizer

from bot_settings import BOT_ID, SLACK_BOT_TOKEN

Base = declarative_base()

class User(Base):
    __tablename__ = "user"
 
    id = Column(Integer, primary_key=True)
    username = Column(String)
    slack_user_id = Column(String)

    MAX_GEN_LEN = 25
 
    def __init__(self, username, slack_user_id):
        """"""
        self.username = username
        self.slack_user_id = slack_user_id
    
    def add_message(self, message, engine):
        lower = message.lower()
        tk = TweetTokenizer()
        spl = tk.tokenize(lower)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Message start token
        exists = session.query(Bigram).filter(Bigram.word_a=='\S', Bigram.word_b==spl[0], Bigram.user_id==self.id)
        if exists.count():
            bg = exists.first()
            bg.count = bg.count+1 
        else:
            bg = Bigram(self.id, '\S', spl[0], 1)
        session.add(bg)
        
        # Rest of message
        for i in range(0, len(spl)):
            word_a = spl[i]
            if i == len(spl)-1:
                word_b = '\E'
            else:
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
    AT_BOT = "<@" + BOT_ID + ">"
    
    def __init__(self):
        # sqlite
        if not os.path.exists(self.DB_NAME):
            self.init_db()
        self.connect_db()
        self.connect_slack()

    def generate_message(self, user=None):
        Session = sessionmaker(bind=self.engine)
        session = Session()
        word_map = defaultdict(list) 
        if user:
            bigrams = session.query(Bigram).filter(Bigram.user_id==user.id)
        else:
            bigrams = session.query(Bigram)
            
        for bg in bigrams:
            key = bg.word_a
            following = bg.word_b
            for i in range(0,bg.count):
                word_map[key].append(following)
            
        # User exists but no corpus, return emtpy string sorry 
        if len(word_map.keys()) == 0:
            return ""

        if '\S' in word_map.keys():
            start = random.choice(word_map['\S'])
        else:
            # TODO deprecate
            start = random.choice(word_map.keys())

        generated = [start]

        while start in word_map.keys() and len(generated) < User.MAX_GEN_LEN:
            next_word = random.choice(word_map[start])

            # short circuit if we happen to reach a message ending token 
            if next_word == '\E':
                return ' '.join(generated)

            # otherwise continue
            generated.append(next_word)
            start = next_word
        
        return ' '.join(generated)
                
    def create_user(self, user_id):
        Session = sessionmaker(bind=self.engine)
        session = Session()
        response = self.slack.users.list()
        users = response.body['members']
        for u in users:
            if u['id'] == user_id:
                user = User(u['name'], user_id)
                session.add(user)
                session.commit()
                return user
                                
    def parse_slack_output(self, output_list):
        Session = sessionmaker(bind=self.engine)
        session = Session()
        if output_list and len(output_list) > 0:
            for output in output_list:
                if output and 'text' in output and 'user' in output:
                    text = output['text']

                    # Don't model yourself 
                    if BOT_ID == output['user']:
                        return

                    if self.AT_BOT in text:
                        parsed = text.split(' ')
                        if len(parsed) == 2:
                            uname = parsed[1]
                            if uname == "-all":
                                gen = "All: "+self.generate_message()
                            else:
                                user = session.query(User).filter(User.username==uname.replace('~',''))
                                if user.count():
                                    user = user.one()
                                    gen = uname+': '+self.generate_message(user=user)
                                else:
                                    gen = "Unknown user: "+uname

                            self.slack_client.api_call("chat.postMessage", channel=output['channel'], text=gen, as_user=True)
                        else:
                            pass
                            # TODO: Error handling?
                    else:
                        userid = output['user']
                        user = session.query(User).filter(User.slack_user_id==userid)
                        if not user.count():
                            user = self.create_user(userid)
                        else:
                            user = user.one()
                        user.add_message(text, self.engine)

    def init_db(self):
        engine = create_engine('sqlite:///'+self.DB_NAME, echo=False)
        Base.metadata.create_all(engine)

    def connect_db(self):
        self.engine = create_engine('sqlite:///'+self.DB_NAME, echo=False)

    def connect_slack(self):
        
        # Connect to regular API
        self.slack = Slacker(SLACK_BOT_TOKEN)
        
        # Connect to real time API
        bot_id = BOT_ID
        self.slack_client = SlackClient(SLACK_BOT_TOKEN)
        READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
        if self.slack_client.rtm_connect():
            print "markovbot is alive"
            while True:
                self.parse_slack_output(self.slack_client.rtm_read())
                time.sleep(READ_WEBSOCKET_DELAY)
        else:
            print "markovbot is dead"

def main():
    MarkovBot()    

if __name__ == "__main__":
    main()
