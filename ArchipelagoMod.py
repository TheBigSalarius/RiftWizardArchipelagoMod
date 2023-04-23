import asyncio
import time

import SteamAdapter
from CommonContent import *
import Level
import Game
import inspect
import json
# Add the base directory to sys.path for testing- allows us to run the mod directly for quick testing
import sys
import ctypes

print("Archipelago Mod loading...")
#TEST REMOVING
sys.path.append('..')

APRemoteCommunication = os.path.join("mods", "ArchipelagoMod", "AP")
APLocalCommunication = os.path.join("mods", "ArchipelagoMod", "local")
SlotDataPath = os.path.join(APRemoteCommunication, "AP_settings.json")
APSettingsFile = "AP_settings.json"
APManaDotFile = "AP_18001.item"
APDoubleManaDotFile = "AP_18002.item"
LastCheckedFloor = "last_checked_floor"
LastCheckedManaDot = "last_checked_manadot"
FixLevelSkip = 0
LastPickupTime = 0
FloorGoalStatus = -1
FloorGoal = -1
LocationOffset = 18000

frm = inspect.stack()[-1]
RiftWizard = inspect.getmodule(frm[0])


# Replaces the Mana Dot icon with the AP icon and modifies the description
def on_init(self):
    self.name = "AP Item"
    self.sprite = Sprite(chr(249), color=COLOR_MANA)
    self.description = "Grants an Archipelago Item"
    self.asset = ["ArchipelagoMod", "AP"]


Level.ManaDot.__init__ = on_init


def check_connection():
    while not os.path.isfile(os.path.join(APRemoteCommunication, APSettingsFile)):
        ctypes.windll.user32.MessageBoxW(
            0, "Disconnected: Ensure the RiftWizardClient is connected.", "Rift Wizard", 0x00001000)
        time.sleep(1)

# Victory check when finishing a floor when the goal is based on floor
def on_enter_portal_goal(self, player):
    if self.reroll:
        self.next_level = None

    if not self.locked:
        if (FixLevelSkip + 1) == FloorGoal and FloorGoalStatus == 1:
            RiftWizard.main_view.play_sound('victory_new')
            RiftWizard.main_view.game.victory = True
            RiftWizard.main_view.game.finalize_save(victory=True)
        else:
            self.level.cur_portal = self


Level.Portal.on_player_enter = on_enter_portal_goal


# This is called when player enters the Mana Dot item square.
def ap_on_player_enter(self, player):
    # These are used to calculate the current floor/dot for location reward, the FixLevelSKip addresses the bug
    # when you step through to the next floor and start on a Mana Dot because your "floor" between floors is 0
    last_checked_floor_path = os.path.join(APLocalCommunication, LastCheckedFloor)
    last_checked_manadot_path = os.path.join(APLocalCommunication, LastCheckedManaDot)

    # Check to ensure Client is connected
    check_connection()

    # This can be done better I'm sure but leverages files to support closing and continuing a run later on
    with open(last_checked_floor_path, "r") as e:
        last_floor = int(e.read())
    if self.level.level_no == 0:
        with open(last_checked_floor_path, 'w') as o:
            o.write(str(FixLevelSkip + 1))
        with open(last_checked_manadot_path, 'w') as p:
            p.write('1')
    elif self.level.level_no > last_floor:
        with open(last_checked_floor_path, 'w') as f:
            f.write(str(self.level.level_no))
        with open(last_checked_manadot_path, 'w') as g:
            g.write('1')
    elif self.level.level_no == last_floor:
        with open(last_checked_manadot_path, "r") as h:
            last_dot = int(h.read())
        with open(last_checked_manadot_path, 'w') as i:
            i.write(str(last_dot + 1))
    with open(last_checked_floor_path, "r") as j:
        check_calc_floor = int(j.read())
    with open(last_checked_manadot_path, 'r') as k:
        check_calc_dot = int(k.read())

    # Creates send#### file in the remote folder to send that location
    create_check_file_name = str(((check_calc_floor - 1) * 3) + check_calc_dot + LocationOffset)
    with open((os.path.join(APRemoteCommunication, ("send" + create_check_file_name))), 'w') as z:
        z.write("")
    self.level.remove_prop(self)
    self.level.event_manager.raise_event(EventOnItemPickup(self), player)


Level.ManaDot.on_player_enter = ap_on_player_enter


def process_mana_file(self, item_file, xp_per_pickup):
    global LastPickupTime
    if os.path.isfile(os.path.join(APRemoteCommunication, item_file)):
        with open(os.path.join(APRemoteCommunication, item_file), "r") as a:
            while True:
                try:
                    remote_manadot = int(a.read())
                    break
                except ValueError:
                    # handle empty file state
                    print("File is empty. Retrying...")
                    time.sleep(.1)
                    a.seek(0)
            if not os.path.isfile(os.path.join(APLocalCommunication, item_file)):
                with open((os.path.join(APLocalCommunication, item_file)), 'w') as b:
                    b.write('0')
                    b.close()
            with open(os.path.join(APLocalCommunication, item_file), "r") as c:
                local_manadot = int(c.read())
                c.close()
                if remote_manadot > local_manadot:
                    with open((os.path.join(APLocalCommunication, item_file)), 'w') as d:
                        d.write(str((int(local_manadot) + 1)))
                        d.close()
                        if time.time() - LastPickupTime >= 1:
                            RiftWizard.main_view.play_sound("item_pickup")
                            LastPickupTime = time.time()
                        self.p1.xp += xp_per_pickup


# This loops nonstop when in game, checks for files to award received items
def ap_is_awaiting_input(self):
    global FixLevelSkip
    global FloorGoalStatus
    global FloorGoal

    # Fixes an issue where the level is 0 inbetween levels and the level is 0 when dropped on an item on a new floor
    FixLevelSkip = RiftWizard.main_view.game.level_num

    check_connection()

    # Checks for if the goal is floor instead of Mordred (on/off initial check)
    if FloorGoalStatus == -1:
        if os.path.isfile(SlotDataPath):
            with open(SlotDataPath, "r") as q:
                data = json.load(q)
                FloorGoalStatus = data["goal"]
                # print("Goal Status Set: ", FloorGoalStatus)

    # Checks for the floor goal # if the goal is floor instead of Mordred (initial check)
    if FloorGoalStatus == 1 and FloorGoal == -1:
        if os.path.isfile(SlotDataPath):
            with open(SlotDataPath, "r") as s:
                data = json.load(s)
                FloorGoal = data["floor_goal"]
                # print("Floor Goal Set: ", FloorGoal)

    process_mana_file(self, APManaDotFile, 1)
    process_mana_file(self, APDoubleManaDotFile, 2)

    # Receive Deathlink death
    if os.path.isfile(os.path.join(APRemoteCommunication, "deathlink")) and not self.deploying:
        RiftWizard.main_view.play_music('lose')
        RiftWizard.main_view.play_sound("death_player")
#        RiftWizard.main_view.game.deploying = False
        self.gameover = True
        self.finalize_save(victory=False)
        os.remove(os.path.join(APRemoteCommunication, "deathlink"))

    # Write victory file for client on game victory
    if self.victory:
        with open((os.path.join(APRemoteCommunication, "victory")), 'w') as v:
            v.write("")
            v.close()
        return True

    if self.next_level:
        return True

    return self.cur_level.is_awaiting_input

    print(RiftWizard.main_view.game.state)
    #print(self.state)

Game.Game.is_awaiting_input = ap_is_awaiting_input


def check_triggers_ap(self):
    # This is vanilla behavior
    if self.cur_level.cur_portal and not self.deploying:
        self.enter_portal()

    if all([u.team == TEAM_PLAYER for u in self.cur_level.units]):

        if not self.has_granted_xp:
            self.has_granted_xp = True
            self.victory_evt = True
            self.finalize_level(victory=True)

    # Sends deathlink when hp = 0
    if self.p1.cur_hp <= 0:
        self.gameover = True
        if not os.path.isfile(os.path.join(APRemoteCommunication, "deathlinkout")):
            with open((os.path.join(APRemoteCommunication, "deathlinkout")), 'w') as z:
                z.close()
        self.finalize_save(victory=False)

    # Trigger victory on Mordred death
    if self.level_num == LAST_LEVEL and not any(u.name == "Mordred" for u in self.cur_level.units):
        self.victory = True
        self.victory_evt = True
        self.finalize_save(victory=True)


Game.Game.check_triggers = check_triggers_ap


# Clears previous runs data when starting new game
def ap_subscribe_mutators(self):
    for mutator in self.mutators:
        for event_type, handler in mutator.global_triggers.items():
            self.cur_level.event_manager.register_global_trigger(event_type, handler)
    if not os.path.exists(APLocalCommunication):
        os.makedirs(APLocalCommunication)
    if not Game.can_continue_game():
        file_list = os.listdir(APLocalCommunication)
        for file_name in file_list:
            file_path = os.path.join(APLocalCommunication, file_name)
            os.remove(file_path)
    if not os.path.isfile(os.path.join(APLocalCommunication, LastCheckedFloor)):
        with open((os.path.join(APLocalCommunication, LastCheckedFloor)), 'w') as m:
            m.write('0')
            m.close()
    if not os.path.isfile(os.path.join(APLocalCommunication, LastCheckedManaDot)):
        with open((os.path.join(APLocalCommunication, LastCheckedManaDot)), 'w') as n:
            n.write('0')
            n.close()


Game.Game.subscribe_mutators = ap_subscribe_mutators


# Everything below is for disabling Achievements/Steam Achievements/Vanilla unlocks (prevents mod messing with stats)
def try_get_sw_disable():
    pass


SteamAdapter.try_get_sw = try_get_sw_disable


def set_stat_disable(stat, val):
    pass


SteamAdapter.set_stat = set_stat_disable


def set_presence_menu_disable():
    pass


SteamAdapter.set_presence_menu = set_presence_menu_disable


def set_trial_complete_disable(trial_name):
    pass


SteamAdapter.set_trial_complete = set_trial_complete_disable
