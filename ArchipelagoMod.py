import asyncio
import time

import pygame

import Consumables
import SteamAdapter
from CommonContent import *
import Level
import Game
import inspect
import json
# Add the base directory to sys.path for testing- allows us to run the mod directly for quick testing
import sys
import ctypes
from Monsters import MordredCorruption

from Consumables import all_consumables, mana_potion, heal_potion
from RiftWizard import CHAR_HEART
from RiftWizard import CHAR_SHIELD
from RiftWizard import COLOR_XP
from RiftWizard import SpellCharacterWrapper
from RiftWizard import OPTIONS_TARGET
from RiftWizard import INSTRUCTIONS_TARGET
from RiftWizard import CHAR_SHEET_TARGET


print("Archipelago Mod loading...")
# TEST REMOVING
sys.path.append('..')


SlotDataPath = os.path.join("mods", "ArchipelagoMod", "AP", "AP_settings.json")



APSettingsFile = "AP_settings.json"
APManaDotFile = "AP_18001.item"
APDoubleManaDotFile = "AP_18002.item"
APConsumableFile = "AP_18003.item"
APTrapFile = "AP_18004.item"
LastCheckedFloor = "last_checked_floor"
LastCheckedManaDot = "last_checked_manadot"
FixLevelSkip = 0
LastPickupTime = 0
FloorGoalStatus = -1
FloorGoal = -1
ConsumableCount = -1
ConsumableCurrentCount = -1
ConsumableSteps = -1
ConsumableCurrentStep = 0
UIPatch = -1
Seed = -1
LocationOffset = 18000

frm = inspect.stack()[-1]
RiftWizard = inspect.getmodule(frm[0])

rand_item_list = all_consumables
rand_item_list.append((mana_potion, Consumables.COMMON))
rand_item_list.append((heal_potion, Consumables.COMMON))


def refresh_consumable_count():
    """ Syncs up the number of completed consumable locally from the server side on a fresh launch """
    global ConsumableCurrentCount
    count = 0
    for filename in os.listdir(APRemoteCommunication):
        if filename.startswith("send") and filename[4:].isdigit():
            file_number = int(filename[4:])
            if file_number >= LocationOffset + 76:
                count += 1
    ConsumableCurrentCount = count


# Replaces the Mana Dot icon with the AP icon and modifies the description
def on_init(self):
    """ Replaces ManaDot with Archipelago Item (visually mostly) """
    self.name = "AP Item"
    self.sprite = Sprite(chr(249), color=COLOR_MANA)
    self.description = "Grants an Archipelago Item"
    self.asset = ["ArchipelagoMod", "AP"]


Level.ManaDot.__init__ = on_init


def check_connection():
    """ Ensures the Rift Wizard Client is running (ensures connection to AP server) Error message until connected"""
    while not os.path.isfile(SlotDataPath):
        ctypes.windll.user32.MessageBoxW(
            0, "Disconnected: Ensure the RiftWizardClient is connected.", "Rift Wizard", 0x00001000)
        time.sleep(1)


# Victory check when finishing a floor when the goal is based on floor
def on_enter_portal_goal(self, player):
    """ Grants victory on entering the required portal when a Floor Goal is set """
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
    """ Handles the behavior of sending location checks when picking up default AP checks (replaced ManaDots)"""
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
             i.write(str(min(last_dot + 1, 3)))
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


# This is called when player enters the Mana Dot item square.
def ap_on_player_enter_consumable(self, player):
    """ Handles granting items normally or recording a consumable as a check (steps count to consumable check) """
    global ConsumableCount
    global ConsumableCurrentCount
    global ConsumableSteps
    global ConsumableCurrentStep
    # Check to ensure Client is connected
    check_connection()

    if ConsumableCurrentCount < ConsumableCount:
        if ConsumableCurrentStep < ConsumableSteps:
            if len(player.items) >= 10 and self.item.name not in [i.name for i in player.items]:
                return

            existing = [i for i in player.items if i.name == self.name]
            if existing:
                if player.stack_max is not None and existing[0].quantity >= player.stack_max:
                    return

            player.add_item(self.item)
            self.level.remove_prop(self)
            self.level.event_manager.raise_event(EventOnItemPickup(self.item), player)
            ConsumableCurrentStep += 1

        elif ConsumableCurrentStep == ConsumableSteps:
            ConsumableCurrentStep = 0
            ConsumableCurrentCount += 1
            create_check_file_name = str(ConsumableCurrentCount + LocationOffset + 75)
            with open((os.path.join(APRemoteCommunication, ("send" + create_check_file_name))), 'w') as z:
                z.write("")
            self.level.remove_prop(self)
            self.level.event_manager.raise_event(EventOnItemPickup(self.item), player)
    else:
        if len(player.items) >= 10 and self.item.name not in [i.name for i in player.items]:
            return

        existing = [i for i in player.items if i.name == self.name]
        if existing:
            if player.stack_max is not None and existing[0].quantity >= player.stack_max:
                return

        player.add_item(self.item)
        self.level.remove_prop(self)
        self.level.event_manager.raise_event(EventOnItemPickup(self.item), player)


Level.ItemPickup.on_player_enter = ap_on_player_enter_consumable


def process_mana_file(self, item_file, xp_per_pickup):
    """ Grants received items from AP checks (ManaDots/DoubleManaDots/Consumables) """
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
                if item_file == APConsumableFile:
                    if remote_manadot > local_manadot:

                        items = [item for item, rarity in all_consumables for _ in range(rarity)]
                        chosen_item = random.choice(items)
                        self.p1.add_item(chosen_item())

                        with open((os.path.join(APLocalCommunication, item_file)), 'w') as d:
                            d.write(str((int(local_manadot) + 1)))
                            d.close()
                            if time.time() - LastPickupTime >= 1:
                                RiftWizard.main_view.play_sound("item_pickup")
                                LastPickupTime = time.time()

                elif item_file == APTrapFile:
                    if remote_manadot > local_manadot:
                            if os.path.isfile(os.path.join(APRemoteCommunication, APTrapFile)) and not self.deploying:
                                spell = MordredCorruption()
                                spell.caster = self.p1
                                self.try_cast(spell, self.p1.x, self.p1.y)
                                with open((os.path.join(APLocalCommunication, item_file)), 'w') as t:
                                    t.write(str((int(local_manadot) + 1)))
                                    t.close()
                else:
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
    """ Main loop - triggers initial value setups from slot data
    UI change for consumables/receiving checks/receiving deathlink/triggering floor based victory,  """
    global FixLevelSkip
    global FloorGoalStatus
    global FloorGoal
    global ConsumableCount
    global ConsumableSteps
    global UIPatch
    global APRemoteCommunication
    global APLocalCommunication
    global Seed

    check_connection()
    # Fixes an issue where the level is 0 inbetween levels and the level is 0 when dropped on an item on a new floor
    FixLevelSkip = RiftWizard.main_view.game.level_num


    if Seed == -1:
        if os.path.isfile(SlotDataPath):
            with open(SlotDataPath, "r") as q:
                data = json.load(q)
                Seed = data["seed"]
                APRemoteCommunication = os.path.join("mods", "ArchipelagoMod", "AP", Seed)
                APLocalCommunication = os.path.join("mods", "ArchipelagoMod", "AP", Seed, "local")

    # Trap logic for Mordred Corruption
    #if os.path.isfile(os.path.join(APRemoteCommunication, APTrapFile)) and not self.deploying:
    #    spell = MordredCorruption()
    #    spell.caster = self.p1
    #    self.try_cast(spell, self.p1.x, self.p1.y)
    #    os.remove(os.path.join(APRemoteCommunication, APTrapFile))

    # Fix since game needs to be launched before UI changes applied
    if UIPatch == -1:
        RiftWizard.main_view.draw_character = draw_character_ap
        UIPatch += 1

    # Checks for the number of consumable checks added
    if ConsumableCount == -1:
        if os.path.isfile(SlotDataPath):
            with open(SlotDataPath, "r") as q:
                data = json.load(q)
                ConsumableCount = data["consumable_count"]
                # print("Goal Status Set: ", FloorGoalStatus)

    if ConsumableCurrentCount == -1:
        refresh_consumable_count()

    # Checks for the number of consumable checks added
    if ConsumableSteps == -1:
        if os.path.isfile(SlotDataPath):
            with open(SlotDataPath, "r") as q:
                data = json.load(q)
                ConsumableSteps = data["consumable_steps"]
                # print("Goal Status Set: ", FloorGoalStatus)

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
    process_mana_file(self, APConsumableFile, 0)
    process_mana_file(self, APTrapFile, 0)

    # Receive Deathlink death
    if os.path.isfile(os.path.join(APRemoteCommunication, "deathlink")) and not self.deploying:
        RiftWizard.main_view.play_music('lose')
        RiftWizard.main_view.play_sound("death_player")
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
    # print(self.state)


Game.Game.is_awaiting_input = ap_is_awaiting_input


def check_triggers_ap(self):
    """ Handles deathlink sending + default behavior """
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
    """ Runs at new game/next floor to ensure base folder is created and tracks last checked location """
    global ConsumableCurrentStep
    global Seed
    global APRemoteCommunication
    global APLocalCommunication
    global APTrapFile

    check_connection()
    if Seed == -1:
        if os.path.isfile(SlotDataPath):
            with open(SlotDataPath, "r") as q:
                data = json.load(q)
                Seed = data["seed"]
    APRemoteCommunication = os.path.join("mods", "ArchipelagoMod", "AP", Seed)
    APLocalCommunication = os.path.join("mods", "ArchipelagoMod", "AP", Seed, "local")

    for mutator in self.mutators:
        for event_type, handler in mutator.global_triggers.items():
            self.cur_level.event_manager.register_global_trigger(event_type, handler)
    if not os.path.exists(APLocalCommunication):
        os.makedirs(APLocalCommunication)
    if not Game.can_continue_game():
        file_list = os.listdir(APLocalCommunication)
        #ConsumableCurrentStep = 0
        for file_name in file_list:
            if file_name != APTrapFile:
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


def draw_character_ap():
    """ Changes the UI to include step to next consumable check """
    RiftWizard.main_view.draw_panel(RiftWizard.main_view.character_display)
    RiftWizard.main_view.char_panel_examine_lines = {}

    cur_x = RiftWizard.main_view.border_margin
    cur_y = RiftWizard.main_view.border_margin
    linesize = RiftWizard.main_view.linesize

    hpcolor = (255, 255, 255)
    if RiftWizard.main_view.game.p1.cur_hp <= 25:
        hpcolor = (255, 0, 0)

    RiftWizard.main_view.draw_string(
        "%s %d/%d" % (CHAR_HEART, RiftWizard.main_view.game.p1.cur_hp, RiftWizard.main_view.game.p1.max_hp),
        RiftWizard.main_view.character_display, cur_x,
        cur_y, color=hpcolor)
    RiftWizard.main_view.draw_string("%s" % CHAR_HEART, RiftWizard.main_view.character_display, cur_x, cur_y,
                                     (255, 0, 0))
    cur_y += linesize

    if RiftWizard.main_view.game.p1.shields:
        RiftWizard.main_view.draw_string("%s %d" % (CHAR_SHIELD, RiftWizard.main_view.game.p1.shields),
                                         RiftWizard.main_view.character_display, cur_x, cur_y)
        RiftWizard.main_view.draw_string("%s" % (CHAR_SHIELD), RiftWizard.main_view.character_display, cur_x, cur_y,
                                         color=COLOR_SHIELD.to_tup())
        cur_y += linesize

    RiftWizard.main_view.draw_string("SP %d" % RiftWizard.main_view.game.p1.xp, RiftWizard.main_view.character_display,
                                     cur_x, cur_y, color=COLOR_XP)
    cur_y += linesize

    RiftWizard.main_view.draw_string("Realm %d" % RiftWizard.main_view.game.level_num,
                                     RiftWizard.main_view.character_display, cur_x, cur_y)
    cur_y += linesize

    # THE ONLY CHANGE TO THE UI
    if ConsumableCurrentCount != ConsumableCount:
        if ConsumableSteps - ConsumableCurrentStep == 0:
            RiftWizard.main_view.draw_string("AP Item Countdown %d" % int(ConsumableSteps - ConsumableCurrentStep),
                                             RiftWizard.main_view.character_display, cur_x, cur_y, (255, 0, 0))
            cur_y += linesize
        else:
            RiftWizard.main_view.draw_string("AP Item Countdown %d" % int(ConsumableSteps - ConsumableCurrentStep),
                                             RiftWizard.main_view.character_display, cur_x, cur_y)
            cur_y += linesize
    #buffs here

    cur_y += linesize

    RiftWizard.main_view.draw_string("Spells:", RiftWizard.main_view.character_display, cur_x, cur_y)
    cur_y += linesize

    # Spells
    index = 1
    for spell in RiftWizard.main_view.game.p1.spells:

        spell_number = (index) % 10
        mod_key = 'C' if index > 20 else 'S' if index > 10 else ''
        hotkey_str = "%s%d" % (mod_key, spell_number)

        if spell == RiftWizard.main_view.cur_spell:
            cur_color = (0, 255, 0)
        elif spell.can_pay_costs():
            cur_color = (255, 255, 255)
        else:
            cur_color = (128, 128, 128)

        fmt = "%2s  %-17s%2d" % (hotkey_str, spell.name, spell.cur_charges)

        RiftWizard.main_view.draw_string(fmt, RiftWizard.main_view.character_display, cur_x, cur_y, cur_color,
                                         mouse_content=SpellCharacterWrapper(spell), char_panel=True)
        RiftWizard.main_view.draw_spell_icon(spell, RiftWizard.main_view.character_display, cur_x + 38, cur_y)

        cur_y += linesize
        index += 1

    cur_y += linesize
    # Items

    RiftWizard.main_view.draw_string("Items:", RiftWizard.main_view.character_display, cur_x, cur_y)
    cur_y += linesize
    index = 1
    for item in RiftWizard.main_view.game.p1.items:

        hotkey_str = "A%d" % (index % 10)

        cur_color = (255, 255, 255)
        if item.spell == RiftWizard.main_view.cur_spell:
            cur_color = (0, 255, 0)
        fmt = "%2s  %-17s%2d" % (hotkey_str, item.name, item.quantity)

        RiftWizard.main_view.draw_string(fmt, RiftWizard.main_view.character_display, cur_x, cur_y, cur_color,
                                         mouse_content=item)
        RiftWizard.main_view.draw_spell_icon(item, RiftWizard.main_view.character_display, cur_x + 38, cur_y)

        cur_y += linesize
        index += 1

    # Buffs
    status_effects = [b for b in RiftWizard.main_view.game.p1.buffs if b.buff_type != BUFF_TYPE_PASSIVE]
    counts = {}
    for effect in status_effects:
        if effect.name not in counts:
            counts[effect.name] = (effect, 0, 0, None)
        _, stacks, duration, color = counts[effect.name]
        stacks += 1
        duration = max(duration, effect.turns_left)

        counts[effect.name] = (effect, stacks, duration, effect.get_tooltip_color().to_tup())

    if status_effects:
        cur_y += linesize
        RiftWizard.main_view.draw_string("Status Effects:", RiftWizard.main_view.character_display, cur_x, cur_y,
                                         (255, 255, 255))
        cur_y += linesize
        for buff_name, (buff, stacks, duration, color) in counts.items():

            fmt = buff_name

            if stacks > 1:
                fmt += ' x%d' % stacks

            if duration:
                fmt += ' (%d)' % duration

            RiftWizard.main_view.draw_string(fmt, RiftWizard.main_view.character_display, cur_x, cur_y, color,
                                             mouse_content=buff)
            cur_y += linesize

    skills = [b for b in RiftWizard.main_view.game.p1.buffs if
              b.buff_type == BUFF_TYPE_PASSIVE]  # and not b.prereq <--errors
    if skills:
        cur_y += linesize

        RiftWizard.main_view.draw_string("Skills:", RiftWizard.main_view.character_display, cur_x, cur_y)
        cur_y += linesize

        skill_x_max = RiftWizard.main_view.character_display.get_width() - RiftWizard.main_view.border_margin - 16
        for skill in skills:
            RiftWizard.main_view.draw_spell_icon(skill, RiftWizard.main_view.character_display, cur_x, cur_y)
            cur_x += 18
            if cur_x > skill_x_max:
                cur_x = RiftWizard.main_view.border_margin
                cur_y += RiftWizard.main_view.linesize

    cur_x = RiftWizard.main_view.border_margin
    cur_y = RiftWizard.main_view.character_display.get_height() - RiftWizard.main_view.border_margin - 3 * RiftWizard.main_view.linesize

    RiftWizard.main_view.draw_string("Menu (ESC)", RiftWizard.main_view.character_display, cur_x, cur_y,
                                     mouse_content=OPTIONS_TARGET)
    cur_y += linesize

    RiftWizard.main_view.draw_string("How to Play (H)", RiftWizard.main_view.character_display, cur_x, cur_y,
                                     mouse_content=INSTRUCTIONS_TARGET)
    cur_y += linesize

    color = RiftWizard.main_view.game.p1.discount_tag.color.to_tup() if RiftWizard.main_view.game.p1.discount_tag else (
    255, 255, 255)
    RiftWizard.main_view.draw_string("Character Sheet (C)", RiftWizard.main_view.character_display, cur_x, cur_y,
                                     color=color,
                                     mouse_content=CHAR_SHEET_TARGET)

    RiftWizard.main_view.screen.blit(RiftWizard.main_view.character_display, (0, 0))


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
