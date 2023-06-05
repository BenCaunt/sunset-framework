
from architecture.architecture_relationships import Command, Subscriber, Topic, Message
from pyros_math.graph_theory import dependecy_sort, cycle_is_present_in_any
from pyros_exceptions.pyros_exceptions import TopicCircularDependency, TopicNameCollision, SubscriberNameCollision
import time
import csv
import json 


class Scheduler:
    def __init__(self):
        self.topics = []
        self.subscribers = []
        self.is_sim = False
        self.throw_exception_on_init_failure = True
        self.root_command = None
        self.writing_file_name = None


    def initialize(self):

        self.topics = dependecy_sort(self.topics)

        if cycle_is_present_in_any(self.topics):
            raise TopicCircularDependency("There is a circular dependency in the topics, aborting init")
        for topic in self.topics:
            print(f'Topic name: {topic.name}')

        self.begin_log()
        self.init_hardware()
        self.check_topic_name_collision()

    def advance_command(self):
        if self.root_command and self.root_command.is_complete():
            self.root_command = self.root_command.next_command

    def periodic(self):

        print(f'self.is_sim: {self.is_sim}')  # Debug
        print(f'self.topics: {self.topics}')  # Debug


        stored_messages = {}
        present_time = time.time()

        if not self.root_command is None and not self.root_command.first_run_occured:
            self.root_command.first_run()
        
        self.advance_command()

        # Check if root_command is still not None after advancing
        if self.root_command is not None:
            self.root_command.periodic()
        else:
            print("No further command to execute")

        for topic in self.topics:
            if self.is_sim and topic.replace_message_with_log:
                # TODO: implement recalling of messages from log file
                pass
            else:
                # if not sim, or if we are not replacing the message with a log, then we need to publish the message since this implies it can be calculated with known inputs
                message, current_time_seconds, delta_time_seconds = topic.publish_periodic()
                stored_messages[topic.name] = f"{json.dumps(message.message)}, {current_time_seconds}, {delta_time_seconds}"
        


        # write the messages to the log file
        if not self.is_sim and stored_messages:
            with open(self.writing_file_name, 'a+') as self.f:
                self.f.write(f"{present_time}, {json.dumps(stored_messages)}\n")

        for sub in self.subscribers:
            sub.periodic()

    def set_command_group(self, head: Command):
        self.root_command = head

    def shutdown(self):
        pass

    # add all topics using args 
    def add_topics(self, *args):
        for topic in args:
            self.topics.append(topic)
    # add all subscribers using args
    def add_subscribers(self, *args):
        for sub in args:
            self.subscribers.append(sub)
    def begin_log(self):
        if not self.is_sim:
            self.writing_file_name = "log_" + str(int(time.time())) + ".csv"
            with open(self.writing_file_name, 'w') as self.f:
                self.f.write("Time, TopicMessageDictionaries\n")

    def init_hardware(self):
        visited_subs = []
        for sub in self.subscribers:
            for sub_other in visited_subs:
                if sub.name == sub_other.name:
                    sub.name = sub.name + "0"
            
            success = sub.initialize_hardware()
            if self.throw_exception_on_init_failure and not success:
                raise RuntimeError(f"Hardware for Subscriber, '{sub.name}' failed to initialize, aborting init")
            sub.is_sim = self.is_sim
    def check_topic_name_collision(self):
        visited_topics = []
        for topic in self.topics:
            for topic_other in visited_topics:
                if topic.name == topic_other.name:
                    raise RuntimeError(f"Two or more Topics cannot have the same name: {topic.name}, Please Check your Configuration")

            visited_topics.append(topic)

            for sub in self.subscribers:
                if topic.name == sub.name:
                    raise RuntimeError(f"Topic and Subscriber cannot have the same name: {topic.name}")
            