import time
import importlib
import logging

from tempora import schedule

import pmxbot


log = logging.getLogger(__name__)


class Bot(pmxbot.core.Bot):
	def __init__(self, server, port, nickname, channels, password=None):
		token = pmxbot.config['slack token']
		sc = importlib.import_module('slackclient')
		self._patch_user(sc)
		self.client = sc.SlackClient(token)
		self.scheduler = schedule.CallbackScheduler(self.handle_scheduled)

	@staticmethod
	def _patch_user(sc):
		"""
		Slack User model doesn't support sending messages, but Channel
		does so copy over the needed method.
		"""
		sc._user.User.send_message = sc._channel.Channel.send_message

	def start(self):
		res = self.client.rtm_connect()
		assert res, "Error connecting"
		self.init_schedule(self.scheduler)
		while True:
			for msg in self.client.rtm_read():
				self.handle_message(msg)
			self.scheduler.run_pending()
			time.sleep(0.1)

	def handle_message(self, msg):
		if msg.get('type') != 'message':
			return
		if not msg.get('user'):
			log.warning("Unknown message %s", msg)
			return
		channel = self.client.server.channels.find(msg['channel']).name
		nick = self.client.server.users.find(msg['user']).name
		self.handle_action(channel, nick, msg['text'])

	def transmit(self, channel, message):
		target = (
			self.client.server.channels.find(channel)
			or self.client.server.users.find(channel)
		)
		target.send_message(message)
