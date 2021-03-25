from __future__ import annotations

import os
import time
import shutil
import json
import requests
import threading
from bs4 import BeautifulSoup

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ListProperty, StringProperty, NumericProperty
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest


CACHE_DIR = "cache"


class CardValue(BoxLayout):
    font_size = NumericProperty(20)
    value = StringProperty("---")
    units = StringProperty("-")


class PlayerCard(BoxLayout):
    name = StringProperty("---")
    avatar_src = StringProperty("assets/avatar.png")
    power = StringProperty("---")
    heart_rate = StringProperty("---")
    cadence = StringProperty("---")
    speed = StringProperty("---")
    time = StringProperty("---")
    distance = StringProperty("---")


class Player:

    RESET_TIMEOUT = 5

    last_updated = None

    player_id = None
    widget = None

    avatar_src = ""
    name = ""
    ftp = None
    weight = None

    world_time = 0

    def __init__(self, player_id):
        self.last_updated = time.time()
        self.player_id = player_id
        self.widget = PlayerCard()
        self.load_player_profile()
        self.reset_clock = Clock.schedule_interval(self.reset, self.RESET_TIMEOUT)

    def fetch_profile_from_zp(self):
        cache_json = os.path.join(CACHE_DIR, f"{self.player_id}.json")

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:86.0) Gecko/20100101 Firefox/86.0"
        }
        resp = requests.get(f"https://zwiftpower.com/profile.php?z={self.player_id}",
                            headers=headers)

        text = resp.text
        soup = BeautifulSoup(text, "html.parser")
        self.name = soup.title.text.split("-")[1].strip()
        img = soup.find('img', class_="img-circle").attrs['src']
        self.avatar_src = os.path.join(CACHE_DIR, f"{img.split('/')[-1]}.jpeg")
        if not os.path.exists(self.avatar_src):
            img_resp = requests.get(img, headers=headers, stream=True)
            if img_resp.status_code == 200:
                with open(self.avatar_src, 'wb') as f:
                    shutil.copyfileobj(img_resp.raw, f)

        with open(cache_json, 'w') as fp:
            json.dump({"name": self.name, "avatar_src": self.avatar_src}, fp)

        self.widget.name = self.name
        self.widget.avatar_src = self.avatar_src

        Clock.schedule_once(self.add_to_layout, 0)

    def load_player_profile(self):

        cache_json = os.path.join(CACHE_DIR, f"{self.player_id}.json")

        if os.path.exists(cache_json):
            with open(cache_json, 'r') as fp:
                cache_json = json.load(fp)
                self.name = cache_json['name']
                self.avatar_src = cache_json['avatar_src']

            Clock.schedule_once(self.add_to_layout, 0)
        else:
            threading.Thread(target=self.fetch_profile_from_zp).start()

        self.widget.name = self.name
        self.widget.avatar_src = self.avatar_src

    def add_to_layout(self, *args):
        self.widget.img.reload()
        App.get_running_app().add_player_widget(self.widget)

    def format_time(self, value):
        mins, sec = divmod(int(value), 60)
        hours, mins = divmod(mins, 60)
        return f"{hours:02}:{mins:02}:{sec:02}"

    def update(self, update):

        if update['world_time'] < self.world_time:
            return

        self.last_updated = time.time()
        self.world_time = update['world_time']
        self.widget.power = str(update['power'])
        self.widget.heart_rate = str(update['heartrate'])
        self.widget.cadence = str(update['cadence'])
        self.widget.distance = str(round(update['distance'] / 1000, 2))
        self.widget.speed = str(round(update['speed'] * 3.6, 2))
        self.widget.time = self.format_time(update['time'])

    def reset(self, *args):
        if time.time() - self.last_updated > self.RESET_TIMEOUT:
            self.last_updated = time.time()
            self.widget.power = "---"
            self.widget.heart_rate = "---"
            self.widget.cadence = "---"
            self.widget.distance = "---"
            self.widget.speed = "---"
            self.widget.time = "---"


class PlayerManager:

    _config = None
    players = {}

    def _log_it(self, *args):
        print(*args)

    def load_players_config(self):

        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)

        with open("players.json", "r") as fp:
            config = json.load(fp)

        self._config = config
        for player_id in self._config["users"]:
            player = Player(player_id)
            self.players[player_id] = player

            UrlRequest('http://127.0.0.1:3030/watch/add', on_error=self._log_it,
                       req_headers={'Content-Type': 'application/json'},  req_body=json.dumps({"id": player_id}))

    def _update_player(self, update):
        player = self.players[update['id']]
        player.update(update)

    def _update_handler(self, req, result):
        for update in result['data']:
            self._update_player(update)

    def update_players(self, *args):
        UrlRequest('http://127.0.0.1:3030/watch', self._update_handler)


class ZwiftTeamView(App):

    players_manager = PlayerManager()
    update_clock = None

    def build(self):
        return Builder.load_file("main.kv")

    def on_start(self):
        self.players_manager.load_players_config()
        self.update_clock = Clock.schedule_interval(self.players_manager.update_players, 0.2)

    def add_player_widget(self, widget):
        self.root.content.add_widget(widget)

    def on_stop(self):
        self.update_clock.cancel()


def run():
    app = ZwiftTeamView()
    app.run()


if __name__ == "__main__":
    Window.clearcolor = (0.1, 0.1, 0.1, .5)
    # Window.borderless = True
    Window.size = (1220, 250)
    run()

