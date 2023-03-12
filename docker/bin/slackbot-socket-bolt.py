#!/usr/local/bin/python3

import json
import logging
import os
import sys
import time
import yaml

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)-8s %(message)s",
)


class slack_scheduler:
    def __init__(self, client, configfile):
        self.client = client
        self.config = self.read_config(configfile)
        self.channels = self.read_channels()
        self.schedule = []

    def read_config(self, configfile):
        with open(configfile) as file:
            if configfile.endswith(".json"):
                config = json.load(file)
            else:
                config = yaml.safe_load(file)

        logging.debug("config: {}".format(config))
        return config

    def read_channels(self):
        result = self.client.conversations_list(types="public_channel,private_channel")
        return {c["id"]: c["name"] for c in result["channels"]}

    def handle_message_in_channel(self, channel, thread_ts, user, text):
        for item in self.config["autoresponse"]:
            if item["pattern"] in text:
                channel_name = self.channels.get(channel, None)
                logging.info("[#{}] add scheduled message".format(channel_name))

                self.schedule.append(
                    {
                        "channel": channel,
                        "thread_ts": thread_ts,
                        "user": user,
                        "time": time.time() + item["delay"],
                        "text": item["message"].get("text", None),
                        "blocks": item["message"].get("blocks", None),
                    }
                )
                return

    def handle_message_in_thread(self, channel, thread_ts, user):
        for i, item in enumerate(self.schedule):
            if (
                item["channel"] == channel
                and item["thread_ts"] == thread_ts
                and item["user"] != user
            ):
                channel_name = self.channels.get(channel, None)
                logging.info("[#{}] delete scheduled message".format(channel_name))

                del self.schedule[i]
                return

    def handle_message(self, event):
        channel_name = self.channels.get(event["channel"], None)
        logging.debug("[#{}] received message: {}".format(channel_name, event["text"]))

        if "thread_ts" in event:
            self.handle_message_in_thread(
                channel=event["channel"],
                thread_ts=event["thread_ts"],
                user=event["user"],
            )
        else:
            self.handle_message_in_channel(
                channel=event["channel"],
                thread_ts=event["event_ts"],
                user=event["user"],
                text=event["text"],
            )

    def handle_member_joined_channel(self, event):
        user = event["user"]
        channel = event["channel"]

        channel_name = self.channels.get(channel, None)
        logging.info("[#{}] somebody joined".format(channel_name))

        if channel_name in self.config["welcome"]:
            logging.info(
                "[#{}] send welcome message to user {}".format(channel_name, user)
            )

            message = self.config["welcome"][channel_name]
            self.client.chat_postEphemeral(channel=channel, user=user, **message)

    def send_scheduled_messages(self):
        deleted_items = []
        for i, item in enumerate(self.schedule):
            if item["time"] < time.time():
                channel_name = self.channels.get(item["channel"], None)
                logging.info("[#{}] send scheduled message".format(channel_name))

                self.client.chat_postMessage(
                    channel=item["channel"],
                    thread_ts=item["thread_ts"],
                    text=item["text"],
                    blocks=item["blocks"],
                )
                deleted_items.append(i)

        for i in reversed(deleted_items):
            del self.schedule[i]

    def loop(self, delay):
        while True:
            time.sleep(delay)
            self.send_scheduled_messages()


def slack_app_initialize(app, scheduler):
    @app.event("member_joined_channel")
    def mention_handler(body, say):
        scheduler.handle_member_joined_channel(body["event"])

    @app.event("message")
    def handle_message_events(body, logger):
        scheduler.handle_message(body["event"])


def main():
    configfile = sys.argv[1]
    app_token = os.environ.get("SLACK_APP_TOKEN")
    bot_token = os.environ.get("SLACK_BOT_TOKEN")

    app = App(token=bot_token)
    scheduler = slack_scheduler(app.client, configfile)
    slack_app_initialize(app, scheduler)

    handler = SocketModeHandler(app, app_token)
    handler.connect()

    scheduler.loop(1)


if __name__ == "__main__":
    main()
