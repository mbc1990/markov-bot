import os
import random
import time
from slackclient import SlackClient
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

    MAX_GEN_LEN = 10
 
    def __init__(self, username):
        """"""
        self.username = username
    
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
    
    def __init__(self):
        # TODO: Connect to slack

        if not os.path.exists(self.DB_NAME):
            self.init_db()

        self.connect_db()
        # create user
        '''
        user = User("testuser")
        self.session.add(user)
        self.session.commit()
        '''

        # print users
        users = self.session.query(User).filter(User.username=="testuser")
        for u in users:
            print "User: "+u.username
            print u.generate_message(self.session)
            #u.add_message("this is a test message", self.session)
        
        # print all bigrams
        '''
        bigrams = self.session.query(Bigram)
        print "printing "+str(bigrams.count())+" bigrams"
        for b in bigrams:
            print b.word_a+' '+b.word_b+' '+str(b.count)
        '''
        # TODO: Initialize markov models for all users    

    def init_db(self):
        print "Creating database"
        engine = create_engine('sqlite:///'+self.DB_NAME, echo=False)
        Base.metadata.create_all(engine)

    def connect_db(self):
        print "Connecting to database"
        engine = create_engine('sqlite:///'+self.DB_NAME, echo=False)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def init_models(self):
        # instantiate instances of MarkovModel for each user 
        print "Initializing instances"
        pass

def main():
    MarkovBot()    

if __name__ == "__main__":
    main()
