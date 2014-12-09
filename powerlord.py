#!/usr/bin/python
#
#POWERLORD
#2014 Russell Mosely

import libtcodpy as libtcod
import math
import textwrap
import shelve

#--------------------
#Window size / camera
#--------------------
SCREEN_WIDTH = 100#100
SCREEN_HEIGHT = 70#70
#Size of the map portion shown on-screen

#--------
#Map size
#--------
MAP_WIDTH = 150#100
MAP_HEIGHT = 150#100

#------------
#GUI elements
#------------
BAR_WIDTH = 20
PANEL_HEIGHT = 9
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH
MSG_HEIGHT = PANEL_HEIGHT - 1
INVENTORY_WIDTH = 50

CAMERA_WIDTH = 80 #63
CAMERA_HEIGHT = SCREEN_HEIGHT - PANEL_HEIGHT

#Set bottom panel to match color of right panel
RIGHT_PANEL_COLOR = libtcod.black
BOTTOM_PANEL_COLOR = RIGHT_PANEL_COLOR

#--------------------------
#Dungeon generator settings
#--------------------------
ROOM_MAX_SIZE = 25
ROOM_MIN_SIZE = 15
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 10
MAX_ROOM_ITEMS = 6
MAX_ROOM_FEATURES = 6

#-----------------------
#Spell ranges and damage
#-----------------------
#Heal spell
HEAL_AMOUNT = 7

#Confuse spell
CONFUSE_RANGE = 4
CONFUSE_NUM_TURNS = 10
CONFUSION_RADIUS = 4

#Lightning spell
LIGHTNING_RANGE = 2
LIGHTNING_DAMAGE = 10

#Fireball spell
FIREBALL_RADIUS = 6
FIREBALL_RANGE = 6
FIREBALL_DAMAGE = 6

#-------------------------
#Player experience stats and caps
#-------------------------
LEVEL_UP_BASE = 150
LEVEL_UP_FACTOR = 100
DUNGEON_LEVEL = 1
dungeon_level = 1

#Spirit values
MAX_SOULS = 10

#----------------
#LIBTCOD settings
#----------------
ANIMATION_FRAMES = 10
FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True  #light walls or not
VIEW_RADIUS = 15
ENEMY_VIEW_RADIUS = 8
LIMIT_FPS = 20  #20 frames-per-second maximum
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

#AI values
AI_INTEREST = 98 #percentage chance per turn that a monster will stay interested in player once out of sight

#-----------
#Wall colors
#-----------
color_dark_wall = libtcod.darker_grey
color_light_wall = libtcod.yellow
color_dark_ground = libtcod.darker_grey * .5
color_light_ground = libtcod.darker_grey
color_ground_texture = libtcod.desaturated_red

FADE_COLOR_TRANSITION = libtcod.black #Color for screen transition

class Tile:
	#a tile of the map and its properties
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked

		#all tiles start unexplored
		self.explored = False

		#by default, if a tile is blocked, it also blocks sight
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight
		self.seen = 0

class Rect:
	#a rectangle on the map. used to characterize a room.
	def __init__(self, x, y, w, h):
		self.x1 = x
		self.y1 = y
		self.x2 = x + w
		self.y2 = y + h

	def center(self):
		center_x = (self.x1 + self.x2) / 2
		center_y = (self.y1 + self.y2) / 2
		return (center_x, center_y)

	def intersect(self, other):
		#returns true if this rectangle intersects with another one
		return (self.x1 <= other.x2 and self.x2 >= other.x1 and
				self.y1 <= other.y2 and self.y2 >= other.y1)

class Object:
	#this is a generic object: the player, a monster, an item, the stairs...
	#it's always represented by a character on screen.
	def __init__(self, x, y, char, name, color, blocks=False, fighter=None, ai=None, item=None):
		self.x = x
		self.y = y
		self.char = char
		self.name = name
		self.color = color
		self.blocks = blocks
		self.fighter = fighter
		if self.fighter:  #let the fighter component know who owns it
			self.fighter.owner = self

		self.ai = ai
		if self.ai:  #let the AI component know who owns it
			self.ai.owner = self

		self.item = item
		if self.item:  #let the Item component know who owns it
			self.item.owner = self

	def move(self, dx, dy):
		#move by the given amount, if the destination is not blocked
		has_turned = False

		if (dx == 1) and (dy == 0) and self.fighter.facing != 1:
			self.fighter.facing = 1
			has_turned = True
		if (dx == 1) and (dy == 1) and self.fighter.facing != 2:
			self.fighter.facing = 2
			has_turned = True
		if (dx == 0) and (dy == 1) and self.fighter.facing != 3:
			self.fighter.facing = 3
			has_turned = True
		if (dx == -1) and (dy == 1) and self.fighter.facing != 4:
			self.fighter.facing = 4
			has_turned = True
		if (dx == -1) and (dy == 0) and self.fighter.facing != 5:
			self.fighter.facing = 5
			has_turned = True
		if (dx == -1) and (dy == -1) and self.fighter.facing != 6:
			self.fighter.facing = 6
			has_turned = True
		if (dx == 0) and (dy == -1) and self.fighter.facing != 7:
			self.fighter.facing = 7
			has_turned = True
		if (dx == 1) and (dy == -1) and self.fighter.facing != 8:
			self.fighter.facing = 8
			has_turned = True

		if not has_turned:
			if not is_blocked(self.x + dx, self.y + dy):
				self.x += dx
				self.y += dy
				self.fighter.tick = self.fighter.tick + self.fighter.move_speed
		else:
			self.fighter.tick = self.fighter.tick + 1

	def move_towards(self, target_x, target_y):
		dx = target_x - self.x
		dy = target_y - self.y
		ddx = 0
		ddy = 0
		if dx > 0:
			ddx = 1
		elif dx < 0:
			ddx = -1
		if dy > 0:
			ddy = 1
		elif dy < 0:
			ddy = -1
		if not is_blocked(self.x + ddx, self.y + ddy):
			self.move(ddx, ddy)
		else:
			if ddx != 0:
				if not is_blocked(self.x + ddx, self.y):
					self.move(ddx, 0)
					return
			if ddy != 0:
				if not is_blocked(self.x, self.y + ddy):
					self.move(0, ddy)
					return

	def distance_to(self, other):
		#return the distance to another object
		dx = other.x - self.x
		dy = other.y - self.y
		return math.sqrt(dx ** 2 + dy ** 2)

	def distance(self, x, y):
		#return the distance to some coordinates
		return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

	def send_to_back(self):
		#make this object be drawn first, so all others appear above it if they're in the same tile.
		global objects
		objects.remove(self)
		objects.insert(0, self)

	def draw(self):
		#only show if it's visible to the player
		if libtcod.map_is_in_fov(fov_map, self.x, self.y):
			(x, y) = to_camera_coordinates(self.x, self.y)
			if x is not None:
				#set the color and then draw the character that represents this object at its position
				if is_in_view(self.x, self.y, player.x, player.y, player.fighter.facing):
					libtcod.console_set_foreground_color(con, self.color)
					libtcod.console_put_char(con, x, y, self.char, libtcod.BKGND_NONE)

				else:
					if self.ai:
						libtcod.console_set_foreground_color(con, libtcod.red)
						libtcod.console_put_char(con, x, y, '?', libtcod.BKGND_NONE)


	def clear(self):
		#erase the character that represents this object
		(x, y) = to_camera_coordinates(self.x, self.y)
		if x is not None:
			libtcod.console_put_char(con, x, y, ' ', libtcod.BKGND_NONE)


class Fighter:
	#combat-related properties and methods (monster, player, NPC).
	def __init__(self, hp, defense, power, xp, move_speed, attack_speed, death_function=None, protected=0):
		self.xp = xp
		self.max_hp = hp
		self.hp = hp
		self.souls = 0
		self.max_souls = MAX_SOULS
		self.defense = defense
		self.power = power
		self.death_function = death_function
		self.facing = libtcod.random_get_int(0, 1, 8)
		self.tick = 0
		self.move_speed = move_speed
		self.attack_speed = attack_speed
		self.protected = protected


	def attack(self, target):
		#a simple formula for attack damage
		damage = libtcod.random_get_int(0, 1, self.power + self.souls) - target.fighter.defense
		if self.souls > self.max_souls:
			self.souls = self.max_souls
		if damage > 0 and target.fighter.protected == 0:
			#make the target take some damage
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.', libtcod.red)
			target.fighter.take_damage(damage)
		elif target.fighter.protected > 0:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but a mysterious force protects him.', libtcod.red)
		else:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!', libtcod.red)
		self.tick = self.tick + self.attack_speed

	def backstab(self, target):
		if target.fighter.protected == 0:
			rand = libtcod.random_get_int(0, 1, 5)
			if rand == 1:
				message(self.owner.name.capitalize() + ' snaps the neck of the ' + target.name + ', killing him instantly!', libtcod.red)
			elif rand == 2:
				message(self.owner.name.capitalize() + ' drives his sword deep into the back of the ' + target.name + '!', libtcod.red)
			elif rand == 3:
				message(self.owner.name.capitalize() + ' obliterates ' + target.name + 'with one savage slash!', libtcod.red)
			elif rand == 4:
				message(self.owner.name.capitalize() + ' targets a vital artery of the ' + target.name + ' with brutal expertise!', libtcod.red)
			elif rand == 5:
				message(self.owner.name.capitalize() + ' guts the unaware ' + target.name + ' with one savage slash!', libtcod.red)
			target.fighter.take_damage(target.fighter.hp)
		elif target.fighter.protected > 0:
			message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but mysterious magic protects him.', libtcod.red)

		self.tick = self.tick + self.attack_speed

	def take_damage(self, damage):
		#apply damage if possible
		if damage > 0:
			self.hp -= damage

			#check for death. if there's a death function, call it
			if self.hp <= 0:
				function = self.death_function
				if function is not None:
					function(self.owner)
				if self.owner != player:  #yield experience to the player
					player.fighter.xp += self.xp

	def heal(self, amount):
		#heal by the given amount, without going over the maximum
		self.hp += amount
		if self.hp > self.max_hp:
			self.hp = self.max_hp

class BasicMonster:
	memory_x = None
	memory_y = None
	broken_los = True

	#AI for a basic monster.
	def take_turn(self):
		#a basic monster takes its turn. if you can see it, it can see you
		monster = self.owner
		#player is in fov and in range
		if (libtcod.map_is_in_fov(fov_map, monster.x, monster.y) and player.distance_to(monster) < ENEMY_VIEW_RADIUS) and (is_in_view(player.x, player.y, monster.x, monster.y, monster.fighter.facing) or not self.broken_los): #either the player is in front of the monster or has been seen previously
			self.memory_x = player.x
			self.memory_y = player.y
			broken_los = False
			#move towards player if far away
			if monster.distance_to(player) >= 2:
				talk = libtcod.random_get_int(0, 1, 200)
				if talk	== 1:
					message(self.owner.name + ': ' + 'The Powerlord!')
				elif talk == 2:
					message('The ' +  self.owner.name + ' draws his blade.')
				elif talk == 3:
					message(self.owner.name + ': ' + 'No mercy!')
				elif talk == 4:
					message(self.owner.name + ': ' + 'Stand and fight!')
				elif talk == 5:
					message(self.owner.name + ': ' + 'You do not stand a chance against me heathen.')
				elif talk == 6:
					message(self.owner.name + ': ' + 'Halt, criminal scum!')
				elif talk == 7:
					message(self.owner.name + ': ' + 'We have you now!')
				elif talk == 8:
					message(self.owner.name + ': ' + 'Its no use!')
				elif talk == 9:
					message(self.owner.name + ': ' + 'Throw down your weapons and I may let you live.')
				elif talk == 10:
					message(self.owner.name + ': ' + 'Run while you still can, coward!')
				monster.move_towards(player.x, player.y)

			#close enough, attack! (if the player is still alive.)
			elif player.fighter.hp > 0:
				monster.fighter.attack(player)

		elif self.memory_x != None and self.memory_y != None and monster.distance(self.memory_x, self.memory_y) > 0:
		#if can't see player but has a memory of player
			self.broken_los = True
			monster.move_towards(self.memory_x, self.memory_y)

		if (monster.x == self.memory_x and monster.y == self.memory_y) or libtcod.random_get_int(0, 0, 100) > AI_INTEREST:
			self.broken_los = True
			self.memory_x = None
			self.memory_y = None

		if self.memory_x == None or self.memory_y == None: #fake a memory so the monster wanders to location in line of sight
			while True:
				x = libtcod.random_get_int(0, monster.x - 10, monster.x + 10)
				y = libtcod.random_get_int(0, monster.y - 10, monster.y + 10)
				if can_walk_between(monster.x, monster.y, x, y): break
			self.broken_los = True
			self.memory_x = x
			self.memory_y = y

class ConfusedMonster:
	#AI for a temporarily confused monster (reverts to previous AI after a while).
	def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
		self.old_ai = old_ai
		self.num_turns = num_turns

	def take_turn(self):
		if self.num_turns > 0:  #still confused...
			#move in a random direction, and decrease the number of turns confused
			self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
			self.num_turns -= 1
			talk = libtcod.random_get_int(0, 1, 10)
			if talk	== 1:
				message('The ' + self.owner.name + ' stumbles in circles.')
			elif talk == 2:
				message('The ' + self.owner.name + ' screams "Run! Its the Powerlord!"')
			elif talk == 3:
				message('The ' + self.owner.name + ' screams incoherently.')

		else:  #restore the previous AI (this one will be deleted because it's not referenced anymore)
			self.owner.ai = self.old_ai
			message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)

class Item:
	#an item that can be picked up and used.
	def __init__(self, use_function=None):
		self.use_function = use_function

	def pick_up(self):
		#add to the player's inventory and remove from the map
		if len(inventory) >= 26:
			message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
		else:
			inventory.append(self.owner)
			objects.remove(self.owner)
			message('You picked up a ' + self.owner.name + '!', libtcod.green)

	def drop(self):
		#add to the map and remove from the player's inventory. also, place it at the player's coordinates
		objects.append(self.owner)
		inventory.remove(self.owner)
		self.owner.x = player.x
		self.owner.y = player.y
		message('You dropped a ' + self.owner.name + '.', libtcod.yellow)

	def use(self):
		#just call the "use_function" if it is defined
		if self.use_function is None:
			message('The ' + self.owner.name + ' cannot be used.')
		else:
			if self.use_function() != 'cancelled':
				inventory.remove(self.owner)  #destroy after use, unless it was cancelled for some reason

def is_blocked(x, y):
	"""Determine if the map tile is blocked.

	Args:
		x: X co-ordinate of map tile.
		y: Y co-ordinate of map tile.
	Returns:
		True if tile is being blocked by an object.

	"""
	
	if map[x][y].blocked:
		return True

	#now check for any blocking objects
	for object in objects:
		if object.blocks and object.x == x and object.y == y:
			return True

	return False

def create_room(room):
	global map
	#go through the tiles in the rectangle and make them passable
	for x in range(room.x1 + 1, room.x2):
		for y in range(room.y1 + 1, room.y2):
			map[x][y].blocked = False
			map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y):
	global map
	#horizontal tunnel. min() and max() are used in case x1>x2
	for x in range(min(x1, x2), max(x1, x2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
	global map
	#vertical tunnel
	for y in range(min(y1, y2), max(y1, y2) + 1):
		map[x][y].blocked = False
		map[x][y].block_sight = False

def make_map():
	global map, objects

	#the list of objects with just the player
	objects = [player]

	#fill map with "blocked" tiles
	map = [[ Tile(True)
		for y in range(MAP_HEIGHT) ]
			for x in range(MAP_WIDTH) ]

	rooms = []
	num_rooms = 0

	for r in range(MAX_ROOMS):
		#random width and height
		w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
		#random position without going out of the boundaries of the map
		x = libtcod.random_get_int(0, 1, MAP_WIDTH - w - 2)
		y = libtcod.random_get_int(0, 1, MAP_HEIGHT - h - 2)

		#"Rect" class makes rectangles easier to work with
		new_room = Rect(x, y, w, h)

		#run through the other rooms and see if they intersect with this one
		failed = False
		for other_room in rooms:
			if new_room.intersect(other_room):
				failed = True
				break

		if not failed:
			#this means there are no intersections, so this room is valid

			#"paint" it to the map's tiles
			create_room(new_room)

			#add some contents to this room, such as monsters, if this isn't the player's starting room
			if num_rooms != 0:
				place_objects(new_room)

			#center coordinates of new room, will be useful later
			(new_x, new_y) = new_room.center()

			if num_rooms == 0:
				#this is the first room, where the player starts at
				player.x = new_x
				player.y = new_y



			else:
				#all rooms after the first:
				#connect it to the previous room with a tunnel

				#center coordinates of previous room
				(prev_x, prev_y) = rooms[num_rooms-1].center()

				#draw a coin (random number that is either 0 or 1)
				if libtcod.random_get_int(0, 0, 1) == 1:
					#first move horizontally, then vertically
					create_h_tunnel(prev_x, new_x, prev_y)
					create_v_tunnel(prev_y, new_y, new_x)
				else:
					#first move vertically, then horizontally
					create_v_tunnel(prev_y, new_y, prev_x)
					create_h_tunnel(prev_x, new_x, new_y)

			#finally, append the new room to the list
			rooms.append(new_room)
			num_rooms += 1
	place_boss(rooms[num_rooms - 1]) #places the boss in the last room we created


def place_boss(room):
	blocked = True
	while blocked:
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
		blocked = is_blocked(x, y)
	fighter_component = Fighter(hp=25, defense=10, power=5, xp=55, death_function=victory_death, move_speed=3, attack_speed=3, protected=0)
	ai_component = BasicMonster()
	monster = Object(x, y, 'C', 'Kodian Leader', libtcod.red, blocks=True, fighter=fighter_component, ai=ai_component)
	objects.append(monster)

	count = 0
	while count < 3:
		while blocked:
			x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
			y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
			blocked = is_blocked(x, y)
		count = count + 1
		fighter_component = Fighter(hp=10, defense=2, power=5, xp=20, death_function=sorcerer_death, move_speed=4, attack_speed=3, protected=0)
		ai_component = BasicMonster()
		monster = Object(x, y, 'S', 'Kodian Ninja Wizard', libtcod.orange, blocks=True, fighter=fighter_component, ai=ai_component)
		objects.append(monster)

def place_objects(room):
	#place random room features
	num_features = libtcod.random_get_int(0, 0, MAX_ROOM_FEATURES)
	for i in range(num_features):
		x = libtcod.random_get_int(0, room.x1 + 2, room.x2-2)
		y = libtcod.random_get_int(0, room.y1 + 2, room.y2-2)
		#only place it if the tile is not blocked
		if not is_blocked(x, y):
			chance = libtcod.random_get_int(0, 0, 110)
			if chance < 10:
				feature = Object(x, y, libtcod.CHAR_BLOCK1, 'pile of rubble', libtcod.light_gray, blocks=True)
			elif chance < 20:
				feature = Object(x, y, libtcod.CHAR_BLOCK2, 'pile of rubble', libtcod.light_gray, blocks=True)
			elif chance < 30:
				feature = Object(x, y, libtcod.CHAR_BLOCK3, 'pile of rubble', libtcod.light_gray, blocks=True)
			elif chance < 40:
				feature = Object(x, y, libtcod.CHAR_ARROW2_N, 'idol', libtcod.light_gray, blocks=True)
			elif chance < 50:
				feature = Object(x, y, libtcod.CHAR_HLINE, 'wizard spellbook', libtcod.light_gray, blocks=True)
			elif chance < 60:
				feature = Object(x, y, libtcod.CHAR_DHLINE, 'mysterious monument', libtcod.light_gray, blocks=True)
			elif chance < 70:
				feature = Object(x, y, libtcod.CHAR_DHLINE, 'mysterious monument', libtcod.light_gray, blocks=True)
			elif chance < 90:
				feature = Object(x, y, 22, 'altar', libtcod.light_gray, blocks=True)
			else:
				feature = Object(x, y, libtcod.CHAR_DHLINE, 'altar', libtcod.light_gray, blocks=True)
			objects.append(feature)

	#choose random number of monsters

	num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

	for i in range(num_monsters):
		#choose random spot for this monster
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

		#only place it if the tile is not blocked
		if not is_blocked(x, y):
			chance = libtcod.random_get_int(0, 0, 100)
			if chance < 50 + 20:  #60% chance of getting a solider
				#create a soldier
				fighter_component = Fighter(hp=10, defense=2, xp=10, power=5, death_function=monster_death, move_speed=3, attack_speed=3, protected=0)
				ai_component = BasicMonster()

				monster = Object(x, y, 's', 'Kodian Soldier', libtcod.white,
					blocks=True, fighter=fighter_component, ai=ai_component)
			elif chance < 50 + 30:
				#create a bandit
				fighter_component = Fighter(hp=5, defense=1, xp=5, power=3, death_function=monster_death, move_speed=5, attack_speed=3, protected=0)
				ai_component = BasicMonster()

				monster = Object(x, y, 'b', 'Kodian Bandit', libtcod.orange,
					blocks=True, fighter=fighter_component, ai=ai_component)
			elif chance < 50 + 40:
				#create a guard
				fighter_component = Fighter(hp=10, defense=1, xp=40, power=3, death_function=monster_death, move_speed=5, attack_speed=3, protected=0)
				ai_component = BasicMonster()

				monster = Object(x, y, 'g', 'Kodian Guard', libtcod.orange,
					blocks=True, fighter=fighter_component, ai=ai_component)

			else:
				#create a knight
				fighter_component = Fighter(hp=20, defense=1, xp=45, power=7, death_function=monster_death, move_speed=3, attack_speed=3, protected=0)
				ai_component = BasicMonster()

				monster = Object(x, y, 'K', 'Kodian Knight', libtcod.dark_orange,
					blocks=True, fighter=fighter_component, ai=ai_component)

			objects.append(monster)


	#choose random number of items
	num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)

	for i in range(num_items):
		#choose random spot for this item
		x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
		y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

		#only place it if the tile is not blocked
		if not is_blocked(x, y):
			dice = libtcod.random_get_int(0, 0, 80)
			if dice < 30:
				#create a stone
				item_component = Item(use_function=throw_stone)
				item = Object(x, y, '*', 'stone', libtcod.grey, item=item_component)
			elif dice < 40:
				#create a healing potion
				item_component = Item(use_function=cast_heal)
				item = Object(x, y, '!', 'healing potion', libtcod.yellow, item=item_component)
			elif dice < 50:
				#create a healing salve
				item_component = Item(use_function=cast_lightning)
				item = Object(x, y, '#', 'Scroll of Storms', libtcod.white, item=item_component)
			elif dice < 60:
				#create a confusion scroll
				item_component = Item(use_function=cast_confuse)
				item = Object(x, y, '#', 'Scroll of Amnesia', libtcod.desaturated_magenta, item=item_component)
			else:
				#create fireball scroll
				item_component = Item(use_function=cast_fireball)
				item = Object(x, y, '#', 'Scroll of Flames', libtcod.desaturated_red, item=item_component)
			objects.append(item)
			item.send_to_back()  #items appear below other objects

def npc_name():


	firstName_bank = ["Karles", "Reto", "Brice", "Malro", "Tericus", "Leb"]
	lastName_bank = ["Alzen", "Lehr", "Jedin", "Cherer", "Delluc", "Seibold"]

	firstName = firstName_bank[libtcod.random_get_int(0,0,len(firstName_bank) - 1)] + " "
	lastName = lastName_bank[libtcod.random_get_int(0,0,len(lastName_bank) - 1)]

	return firstName + lastName

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
	#render a bar (HP, experience, etc). first calculate the width of the bar
	bar_width = int(float(value) / maximum * total_width)

	#render the background first
	libtcod.console_set_background_color(panel, back_color)
	libtcod.console_rect(panel, x, y, total_width, 1, False)

	#now render the bar on top
	libtcod.console_set_background_color(panel, bar_color)
	if bar_width > 0:
		libtcod.console_rect(panel, x, y, bar_width, 1, False)

	#finally, some centered text with the values
	libtcod.console_set_foreground_color(panel, libtcod.white)
	libtcod.console_print_center(panel, x + total_width / 2, y, libtcod.BKGND_NONE,
		name + ': ' + str(value) + '/' + str(maximum))

def get_names_under_mouse():
	#return a string with the names of all objects under the mouse
	mouse = libtcod.mouse_get_status()
	(x, y) = (mouse.cx, mouse.cy)
	(x, y) = (camera_x + x, camera_y + y)  #from screen to map coordinates

	#create a list with the names of all objects at the mouse's coordinates and in FOV
	names = [obj.name for obj in objects
		if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y) and is_in_view(obj.x, obj.y, player.x, player.y, player.fighter.facing)]

	names = ', '.join(names)  #join the names, separated by commas
	return names.capitalize()

def move_camera(target_x, target_y):
	global camera_x, camera_y, fov_recompute

	#new camera coordinates (top-left corner of the screen relative to the map)
	x = target_x - CAMERA_WIDTH / 2  #coordinates so that the target is at the center of the screen
	y = target_y - CAMERA_HEIGHT / 2

	#make sure the camera doesn't see outside the map
	if x < 0: x = 0
	if y < 0: y = 0
	if x > MAP_WIDTH - CAMERA_WIDTH - 1: x = MAP_WIDTH - CAMERA_WIDTH - 1
	if y > MAP_HEIGHT - CAMERA_HEIGHT - 1: y = MAP_HEIGHT - CAMERA_HEIGHT - 1

	if x != camera_x or y != camera_y: fov_recompute = True

	(camera_x, camera_y) = (x, y)

def to_camera_coordinates(x, y):
	#convert coordinates on the map to coordinates on the screen
	(x, y) = (x - camera_x, y - camera_y)

	if (x < 0 or y < 0 or x >= CAMERA_WIDTH or y >= CAMERA_HEIGHT):
		return (None, None)  #if it's outside the view, return nothing

	return (x, y)

def render_all():
	global fov_map, color_dark_wall, color_light_wall
	global color_dark_ground, color_light_ground
	global fov_recompute

	move_camera(player.x, player.y)
	#calculate where monsters can see so it can be displayed
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			map[x][y].seen = 0

	for object in objects:
		libtcod.map_compute_fov(fov_map, player.x, player.y, VIEW_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		if libtcod.map_is_in_fov(fov_map, object.x, object.y) and object.ai and is_in_view(object.x, object.y, player.x, player.y, player.fighter.facing):
			libtcod.map_compute_fov(fov_map, object.x, object.y, ENEMY_VIEW_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
			for y in range(object.y - ENEMY_VIEW_RADIUS, object.y + ENEMY_VIEW_RADIUS + 1):
				for x in range(object.x - ENEMY_VIEW_RADIUS + 1, object.x + ENEMY_VIEW_RADIUS + 1):
					if y > 0 and y < MAP_HEIGHT and x > 0 and x < MAP_WIDTH:
						if libtcod.map_is_in_fov(fov_map, x, y) and is_in_view(x, y, object.x, object.y, object.fighter.facing):
							distance = object.distance(x, y)
							if distance > 0:
								map[x][y].seen += 1 - (1 * (distance / ENEMY_VIEW_RADIUS))
							if map[x][y].seen > 1:
								map[x][y].seen = 1

	if fov_recompute:
	#recompute FOV if needed (the player moved or something)
		fov_recompute = False
		libtcod.map_compute_fov(fov_map, player.x, player.y, VIEW_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
		libtcod.console_clear(con)

		#go through all tiles, and set their background color according to the FOV
		for y in range(CAMERA_HEIGHT):
			for x in range(CAMERA_WIDTH):
				(map_x, map_y) = (camera_x + x, camera_y + y)
				if libtcod.map_is_in_fov(fov_map, map_x, map_y) and is_in_view(map_x, map_y, player.x, player.y, player.fighter.facing):
					visible = True
				else:
					visible = False
				wall = map[map_x][map_y].block_sight
				if not visible:
					#if it's not visible right now, the player can only see it if it's explored
					if map[map_x][map_y].explored:
						if wall:
							libtcod.console_set_back(con, x, y, color_dark_wall, libtcod.BKGND_SET)
						else:
							libtcod.console_set_back(con, x, y, color_dark_ground, libtcod.BKGND_SET)
				else:
					#it's visible
					if wall:
						libtcod.console_set_back(con, x, y, color_light_wall, libtcod.BKGND_SET )
					else:
						if map[map_x][map_y].seen == 0:
							libtcod.console_set_back(con, x, y, color_dark_ground, libtcod.BKGND_SET )
						else:
							libtcod.console_set_back(con, x, y, libtcod.red * map[map_x][map_y].seen, libtcod.BKGND_SET )
						#libtcod.console_set_back(con, x, y, color_ground_texture, libtcod.BKGND_SET )
						libtcod.console_set_fore(con, x, y, color_ground_texture)
						libtcod.console_set_char(con, x, y, '.')
					#since it's visible, explore it
					map[map_x][map_y].explored = True

	#draw all objects in the list, except the player. we want it to
	#always appear over all other objects! so it's drawn later.
	for object in objects:
		if object != player:
			object.draw()
	player.draw()

	#blit the contents of "con" to the root console
	libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)

	#prepare to render the GUI panel
	libtcod.console_set_background_color(panel, RIGHT_PANEL_COLOR)
	libtcod.console_set_background_color(panel_bottom, BOTTOM_PANEL_COLOR)
	libtcod.console_clear(panel_bottom)
	libtcod.console_clear(panel)

	#print 'messages label'
	libtcod.console_set_foreground_color(panel_bottom, libtcod.white)
	libtcod.console_print_left(panel_bottom, 1, 0, libtcod.BKGND_NONE, "" )

	#print the game messages, one line at a time
	y = 1
	mul = 0
	for (line, color) in game_msgs:
		libtcod.console_set_foreground_color(panel_bottom, color * mul)
		libtcod.console_print_left(panel_bottom, 1, y, libtcod.BKGND_NONE, line)
		y += 1
		mul += .2

	#show the player's stats
	render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp,
		libtcod.desaturated_red, libtcod.darker_red)
	render_bar(1, 3, BAR_WIDTH, 'SOULS', player.fighter.souls, player.fighter.max_souls,
		libtcod.desaturated_cyan, libtcod.darker_cyan)
	render_bar(1, 5, BAR_WIDTH, 'EXP', player.fighter.xp, LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR,
		libtcod.dark_yellow, libtcod.darker_yellow)

	#display names of objects under the mouse
	libtcod.console_set_foreground_color(panel, libtcod.light_gray)
	libtcod.console_print_left(panel, 1, 0, libtcod.BKGND_NONE, get_names_under_mouse())

	#blit the contents of "panel" to the root console
	libtcod.console_blit(panel, 0, 0, 20, PANEL_HEIGHT, 0, SCREEN_WIDTH-20, 0 )
	libtcod.console_blit(panel_bottom, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def message(new_msg, color = libtcod.white):
	#split the message if necessary, among multiple lines
	new_msg_lines = textwrap.wrap(new_msg, )

	for line in new_msg_lines:
		#if the buffer is full, remove the first line to make room for the new one
		if len(game_msgs) == MSG_HEIGHT:
			del game_msgs[0]

		#add the new line as a tuple, with the text and the color
		game_msgs.append( (line, color) )

def player_move_or_attack(dx, dy):
	global fov_recompute

	#the coordinates the player is moving to/attacking
	x = player.x + dx
	y = player.y + dy

	#try to find an attackable object there
	target = None
	for object in objects:
		if object.fighter and object.x == x and object.y == y:
			target = object
			break

	#attack if target found, move otherwise
	if target is not None:
		if is_in_view(player.x, player.y, target.x, target.y, target.fighter.facing):
			if libtcod.random_get_int(0, 0, 15) > 1:
				player.fighter.attack(target)
				chance = libtcod.random_get_int(0, 0, 110)
				chance_crit = libtcod.random_get_int(0, 0, 100)
				feature = Object(x, y, libtcod.CHAR_BLOCK1, 'pile of rubble', libtcod.light_gray, blocks=True)

			else:
				message('Your swing misses!!', libtcod.white)
		else:
			player.fighter.backstab(target)
	else:
		player.move(dx, dy)
	fov_recompute = True

def player_pass_turn():
	global fov_recompute

	fov_recompute = True
	player.fighter.tick = player.fighter.tick + player.fighter.move_speed

def closest_monster(max_range):
	#find closest enemy, up to a maximum range, and in the player's FOV
	closest_enemy = None
	closest_dist = max_range + 1  #start with (slightly more than) maximum range

	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			#calculate distance between this object and the player
			dist = player.distance_to(object)
			if dist < closest_dist:  #it's closer, so remember it
				closest_enemy = object
				closest_dist = dist
	return closest_enemy

def menu(header, options, width):
	if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')

	#calculate total height for the header (after auto-wrap) and one line per option
	header_height = libtcod.console_height_left_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
	if header == '':
		header_height = 0
	height = len(options) + header_height

	#create an off-screen console that represents the menu's window
	window = libtcod.console_new(width, height)

	#print the header, with auto-wrap
	libtcod.console_set_foreground_color(window, libtcod.white)
	libtcod.console_print_left_rect(window, 0, 0, width, height, libtcod.BKGND_NONE, header)

	#print all the options
	y = header_height
	letter_index = ord('a')
	for option_text in options:
		text = '(' + chr(letter_index) + ') ' + option_text
		libtcod.console_print_left(window, 0, y, libtcod.BKGND_NONE, text)
		y += 1
		letter_index += 1

	#blit the contents of "window" to the root console
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

	#present the root console to the player and wait for a key-press
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)

	if key.vk == libtcod.KEY_ENTER and key.lalt:  #(special case) Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

	#convert the ASCII code to an index; if it corresponds to an option, return it
	index = key.c - ord('a')
	if index >= 0 and index < len(options): return index
	return None

def inventory_menu(header):
	#show a menu with each item of the inventory as an option
	if len(inventory) == 0:
		options = ['Inventory is empty.']
	else:
		options = [item.name for item in inventory]

	index = menu(header, options, INVENTORY_WIDTH)

	#if an item was chosen, return it
	if index is None or len(inventory) == 0: return None
	return inventory[index].item

def msgbox(text, width=50):
	menu(text, [], width)  #use menu() as a sort of "message box"

#Show help menu when player presses forward for the first time
global tut
tut = True
def handle_keys():
	global  tut
	key = libtcod.console_check_for_keypress(libtcod.KEY_PRESSED)

	if key.vk == libtcod.KEY_ENTER and key.lalt:
		#Alt+Enter: toggle fullscreen
		libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

	elif key.vk == libtcod.KEY_ESCAPE:
		return 'exit'  #exit game

	if game_state == 'playing':
		key_char = chr(key.c)

		if libtcod.Key:
			if tut == True:

					help_menu()

					tut = False

		#movement keys
		if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8 or key_char == 'k':
			player_move_or_attack(0, -1)



		elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2 or key_char == 'j':
			player_move_or_attack(0, 1)

		elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4 or key_char == 'h':
			player_move_or_attack(-1, 0)

		elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6 or key_char == 'l':
			player_move_or_attack(1, 0)

		elif key.vk == libtcod.KEY_KP1 or key_char == 'b':
			player_move_or_attack(-1, 1)

		elif key.vk == libtcod.KEY_KP3 or key_char == 'n':
			player_move_or_attack(1, 1)

		elif key.vk == libtcod.KEY_KP7 or key_char == 'y':
			player_move_or_attack(-1, -1)

		elif key.vk == libtcod.KEY_KP9 or key_char == 'u':
			player_move_or_attack(1, -1)

		elif key.vk == libtcod.KEY_KP5 or key_char == '.':
			player_pass_turn()


		else:
			#test for other keys

			if key_char == 'g':
				#pick up an item
				for object in objects:  #look for an item in the player's tile
					if object.x == player.x and object.y == player.y and object.item:
						object.item.pick_up()
						break

			if key_char == 'i':
				#show the inventory; if an item is selected, use it
				chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.use()

			if key_char == 'd':
				#show the inventory; if an item is selected, drop it
				chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
				if chosen_item is not None:
					chosen_item.drop()

			if key_char == '?':
				#go to help menu
				help_menu()

			if key_char == 'c':
				#show character information
				level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
				msgbox('Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
					'\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
					'\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)

			return 'didnt-take-turn'

def player_death(player):
	#the game ended!
	global game_state
	message('The Powerlord is no more!', libtcod.red)
	game_state = 'dead'

	#for added effect, transform the player into a corpse!
	player.char = '%'
	player.color = libtcod.red

	fade_effect(libtcod.darker_red, 0)
	#main_menu()

def monster_death(monster):
	explosion_effect(monster.x, monster.y, 1, libtcod.red, color_light_ground)
	player.fighter.souls += 1
	if player.fighter.souls > MAX_SOULS:
		player.fighter.souls = 10

	message('Your blade absorbs the soul of the ' + monster.name.capitalize() + '!', libtcod.orange)
	message('The ' + monster.name + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points.', libtcod.orange)
	monster.char = '%'
	monster.color = libtcod.red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()

def sorcerer_death(monster):
	for obj in objects:
		if obj.fighter:
			if obj.fighter.protected > 0:
				obj.fighter.protected = obj.fighter.protected - 1
	explosion_effect(monster.x, monster.y, 2, libtcod.red, color_light_ground)
	explosion_effect(player.x, player.y, 6, libtcod.cyan, color_light_ground)
	monster.char = '%'
	monster.color = libtcod.red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()

def victory_death(monster):
	global dungeon_level

	#should be called when the final boss is dead
	message('With the death of the ' + monster.name.capitalize() + ' you descend deeper into the depths of the fortress. ', libtcod.yellow)
	message('You have been healed for half of your health.', libtcod.red)
	player.fighter.heal(player.fighter.max_hp / 2)  #heal the player by 50%
	game_state = 'victory'
	monster.char = '%'
	monster.color = libtcod.red
	monster.blocks = False
	monster.fighter = None
	monster.ai = None
	monster.name = 'remains of ' + monster.name
	monster.send_to_back()
	dungeon_level += 1
	print("You are are level " + str(dungeon_level))
	make_map()
	initialize_fov()

def check_level_up():
	#see if the player's experience is enough to level-up
	level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
	if player.fighter.xp >= level_up_xp:
		#it is! level up
		player.level += 1
		player.fighter.xp -= level_up_xp
		message('Your battle skills grow stronger! You reached level ' + str(player.level) + '!', libtcod.yellow)
		choice = None
		while choice == None:  #keep asking until a choice is made
			choice = menu('Level up! Choose a stat to raise:\n',
				['Constitution (+20 HP, from ' + str(player.fighter.max_hp) + ')',
				'Strength (+1 attack, from ' + str(player.fighter.power) + ')',
				'Agility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)

		if choice == 0:
			player.fighter.max_hp += 20
			player.fighter.hp += 20
		elif choice == 1:
			player.fighter.power += 1
		elif choice == 2:
			player.fighter.defense += 1

def target_tile(max_range=None):
	#return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked.
	while True:
		#render the screen. this erases the inventory and shows the names of objects under the mouse.
		render_all()
		libtcod.console_flush()

		key = libtcod.console_check_for_keypress()
		mouse = libtcod.mouse_get_status()  #get mouse position and click status
		(x, y) = (mouse.cx, mouse.cy)
		(x, y) = (camera_x + x, camera_y + y)  #from screen to map coordinates

		if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
			return (None, None)  #cancel if the player right-clicked or pressed Escape

		#accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
		if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
			(max_range is None or player.distance(x, y) <= max_range)):
			return (x, y)

def target_monster(max_range=None):
	#returns a clicked monster inside FOV up to a range, or None if right-clicked
	while True:
		(x, y) = target_tile(max_range)
		if x is None:  #player cancelled
			return None

		#return the first clicked monster, otherwise continue looping
		for obj in objects:
			if obj.x == x and obj.y == y and obj.fighter and obj != player:
				return obj

def closest_monster(max_range):
	#find closest enemy, up to a maximum range, and in the player's FOV
	closest_enemy = None
	closest_dist = max_range + 1  #start with (slightly more than) maximum range

	for object in objects:
		if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
			#calculate distance between this object and the player
			dist = player.distance_to(object)
			if dist < closest_dist:  #it's closer, so remember it
				closest_enemy = object
				closest_dist = dist
	return closest_enemy

def throw_stone():
	#throws a stone! hopefully distracts an enemy as well
	#ask the player for a target to throw to
	message('Left-click to choose where to throw the stone, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()
	for obj in objects:  #affects every enemy within range if they can't see the player
		if obj.distance(x, y) <= ENEMY_VIEW_RADIUS and obj.ai:
			if not (libtcod.map_is_in_fov(fov_map, obj.x, obj.y) and is_in_view(player.x, player.y, obj.x, obj.y, obj.fighter.facing) and player.distance_to(obj) < ENEMY_VIEW_RADIUS):
				obj.ai.memory_x = x
				obj.ai.memory_y = y
				message('The ' + obj.name + ' is distracted by the noise!', libtcod.light_green)

def cast_heal():
	"""

	Heals the player for a set amount.

	HEAL_AMOUNT
	Amount of health to heal.
	"""
	if player.fighter.hp == player.fighter.max_hp:
		message('You are already at full health.', libtcod.red)
		return 'cancelled'
	else:
		message('Your wounds start to feel better!', libtcod.light_violet)
		player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
	"""

	Find the closest enemy within LIGHTNING_RANGE and do damage to it.

	LIGHTNING_RANGE
		Maximum range of the spell.
	LIGHTNING_DAMAGE
		Damage to enemy caused by spell.
	"""
	monster = closest_monster(LIGHTNING_RANGE)
	if monster is None:  #no enemy found within maximum range
		message('No enemy is close enough to strike.', libtcod.red)
		return 'cancelled'
	else:
		explosion_effect(monster.x, monster.y, 5, libtcod.white, color_light_ground)
		#zap it!
		message('A lighting bolt strikes the ' + monster.name + ' for ' + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
		monster.fighter.take_damage(LIGHTNING_DAMAGE)
		player.fighter.souls = 0

def cast_fireball():
	"""

	Ask player to determine target before casting fireball spell.

	FIREBALL_RADIUS
		Radius of fireball spell.
	FIREBALL_DAMAGE
		Damage caused by the spell.
	"""
	message('Left-click to choose where to cast this spell, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()

	if x is None: return 'cancelled'
	message('A fireball suddenly appears, engulfing your target!', libtcod.light_green)
	explosion_effect(x, y, CONFUSION_RADIUS, libtcod.light_orange, libtcod.red)

	for obj in objects:  #damage every fighter in range, including the player
		if obj.distance(x, y) <= FIREBALL_RADIUS and obj.ai:
			message(obj.name + ' hit by fire for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.light_blue)
			obj.fighter.take_damage(FIREBALL_DAMAGE + int(player.fighter.souls/2))
	player.fighter.souls = 0

def cast_confuse():
	"""

	Ask player to determine target before casting spell.

	CONFUSION_RADIUS
	Radius of confusion spell.
	"""
	message('Left-click to choose where to cast this spell, or right-click to cancel.', libtcod.light_cyan)
	(x, y) = target_tile()

	if x is None: return 'cancelled'
	message('A flash of while light suddenly appears and vanishes.', libtcod.light_green)
	explosion_effect(x, y, CONFUSION_RADIUS, libtcod.dark_grey, libtcod.white)

	for obj in objects:  #damage  every fighter in range, including the player
		if obj.distance(x, y) <= CONFUSION_RADIUS and obj.ai:
			#replace the monster's AI with a "confused" one; after some turns it will restore the old AI
			old_ai = obj.ai
			obj.ai = ConfusedMonster(old_ai)
			obj.ai.owner = obj  #tell the new component who owns it
			message('The eyes of the ' + obj.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)

def explosion_effect(cx, cy, radius, inner_color, outer_color):
	global fov_recompute
	render_all()  #first, re-render the screen
	num_frames = float(ANIMATION_FRAMES)  #number of frames as a float, so dividing an int by it doesn't yield an int

	for frame in range(ANIMATION_FRAMES):
		#loop through all tiles in a square around the center. min and max make sure it doesn't go out of the map.
		for y in range(CAMERA_HEIGHT):
			#THis is the rang eof the camera
			for x in range(CAMERA_WIDTH):
				(map_x, map_y) = (camera_x + x, camera_y + y)
				#only draw on visible floor tile
				if not map[map_x][map_y].blocked and libtcod.map_is_in_fov(fov_map, map_x, map_y):
					#interpolate between inner and outer color
					r = 0.5 * radius * frame/num_frames  #the radius expands as the animation advances
					sqr_dist = (map_x - cx) ** 2 + (map_y - cy) ** 2  #the squared distance from tile to center
					#alpha increases with radius (0.9*r) and decreases with distance to center. the +0.1 prevents a division by 0 at the center.
					alpha = (0.9*r) ** 2 / (sqr_dist + 0.1)
					color = libtcod.color_lerp(outer_color, inner_color, min(1, alpha))  #interpolate colors. also prevent alpha > 1.
					#interpolate between previous color and ground color (fade away from the center)
					alpha = r ** 2 / (sqr_dist + 0.1)  #same as before, but with the full radius (r) instead of (0.9*r)
					alpha = min(alpha, 4*(1 - frame/num_frames))  #impose on alpha an upper limit that decreases as the animation advances, so it fades out in the end
					color = libtcod.color_lerp(color_light_ground, color, min(1, alpha))  #same as before
					libtcod.console_set_back(con, x, y, color, libtcod.BKGND_SET)  #set the tile color
					libtcod.console_blit(con, 0, 0, CAMERA_WIDTH, CAMERA_HEIGHT, 0, 0, 0)
		libtcod.console_check_for_keypress()
		libtcod.console_flush()  #show result
	fov_recompute = True #repair the damage
	render_all()
	libtcod.console_flush()

def fade_effect(color, direction, forward_count=255, backwards_count=0):
	"""
	Set console color to COLOR based on 255 frames.
	255 = solid color

	:param color:
	 	Color to fade to.
	:param count:
	 	Color value to start at (almost always will be 0)
	:param direction:
		Direction to transition color:
			0 = fade to color
			1 = fade from color
	:return:
		Returns color value to console.
	"""
	if direction == 0:
		while forward_count > backwards_count:
			libtcod.console_set_fade(forward_count,color)
			libtcod.console_flush()
			forward_count -= 5
	elif direction == 1:
		while backwards_count < forward_count:
			libtcod.console_set_fade(backwards_count,color)
			libtcod.console_flush()
			backwards_count += 5
			libtcod.console_set_fade(255, FADE_COLOR_TRANSITION)
	else:
		print "DEBUG: Fade effect"

def is_in_view(x1, y1, x2, y2, facing):
	delta_x = x1 - x2
	delta_y = y1 - y2
	angle = math.degrees(math.atan2(delta_y, delta_x))
	if (delta_x == 0) and (delta_y == 0):
		return True
	if facing == 1:
		if (angle < 60) and (angle > -60):
			return True
	if facing == 2:
		if (angle < 105) and (angle > -15):
			return True
	if facing == 3:
		if (angle < 150) and (angle > 30):
			return True
	if facing == 4:
		if ((angle <= 180) and (angle > 75)) or ((angle >= -180) and (angle < -165)):
			return True
	if facing == 5:
		if ((angle > 120) and (angle <= 180)) or ((angle < -120) and (angle >= -180)):
			return True
	if facing == 6:
		if ((angle > 165) and (angle <= 180)) or ((angle < -75) and (angle >= -180)):
			return True
	if facing == 7:
		if (angle > -150) and (angle < -30):
			return True
	if facing == 8:
		if (angle > -105) and (angle < 15):
			return True
	return False

def can_walk_between(x1, y1, x2, y2):
	libtcod.line_init(x1, y1, x2, y2)
	test = True
	while True:
		(x, y) = libtcod.line_step()
		if x is None: break

		if is_blocked(x, y):
			test = False
			break
	return test

def help_menu():
	#create an off-screen console that represents the menu's window
	width = 42
	height = 15
	window = libtcod.console_new(width, height)

	#print the header, with auto-wrap
	libtcod.console_set_foreground_color(window, libtcod.white)
	libtcod.console_print_center(window, 18, 0, libtcod.BKGND_NONE, 'LIST OF COMMANDS')

	#print all the options
	libtcod.console_print_left(window, 0, 2, libtcod.BKGND_NONE, 'Arrow keys or hjkl + yubn to move.')
	libtcod.console_print_left(window, 0, 4, libtcod.BKGND_NONE, 'g: pick get items on the ground.')
	libtcod.console_print_left(window, 0, 5, libtcod.BKGND_NONE, 'i: use items in inventory.')
	libtcod.console_print_left(window, 0, 6, libtcod.BKGND_NONE, 'd: drop items from inventory.')
	libtcod.console_print_left(window, 0, 7, libtcod.BKGND_NONE, '. or num-pad 5: pass a turn.')
	libtcod.console_print_left(window, 0, 8, libtcod.BKGND_NONE, 'Alt-enter: Switch to and from full-screen.')
	libtcod.console_print_left(window, 0, 10, libtcod.BKGND_NONE, 'Use the mouse to look around and aim.')


	#blit the contents of "window" to the root console
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

	#present the root console to the player and wait for a key-press
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)

def npc_dialog():
	#create an off-screen console that represents the menu's window
	width = 42
	height = 15
	window = libtcod.console_new(width, height)


	#print the header, with auto-wrap
	libtcod.console_set_foreground_color(window, libtcod.white)
	libtcod.console_print_center(window, 18, 0, libtcod.BKGND_NONE, 'YOU ARE THE POWERLORD')

	#print all the options
	libtcod.console_print_center(window, 0, 2, libtcod.BKGND_NONE, "THis is a test you failed")

	#blit the contents of "window" to the root console
	x = SCREEN_WIDTH/2 - width/2
	y = SCREEN_HEIGHT/2 - height/2
	libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

	#present the root console to the player and wait for a key-press
	libtcod.console_flush()
	key = libtcod.console_wait_for_keypress(True)

def save_game():
	#open a new empty shelve (possibly overwriting an old one) to write the game data
	file = shelve.open('savegame', 'n')
	file['map'] = map
	file['objects'] = objects
	file['player_index'] = objects.index(player)  #index of player in objects list
	file['inventory'] = inventory
	file['game_msgs'] = game_msgs
	file['game_state'] = game_state
	file['dungeon_level'] = dungeon_level
	file.close()

def load_game():
	#open the p  objects, player, stairs, inventory, game_msgs, game_state

	file = shelve.open('savegame', 'r')
	map = file['map']
	objects = file['objects']
	player = objects[file['player_index']]  #get index of player in objects list and access it
	inventory = file['inventory']
	game_msgs = file['game_msgs']
	game_state = file['game_state']
	dungeon_level = file['dungeon_level']
	file.close()

	initialize_fov()

def new_game():
	global player, inventory, game_msgs, game_state, num_directions, directions, facings, unit_directions


	#create object representing the player
	fighter_component = Fighter(hp=100, defense=2, power=7, xp=0,  death_function=player_death, move_speed=3, attack_speed=3, protected=0)
	player = Object(0, 0, '@', 'The Powerlord', libtcod.white, blocks=True, fighter=fighter_component)
	player.level = 1

	#generate map (at this point it's not drawn to the screen)
	make_map()
	initialize_fov()

	game_state = 'playing'
	inventory = []

	#create the list of game messages and their colors, starts empty
	game_msgs = []

	#a warm welcoming message!
	message('You kick open the gates of Castle Kovia, your blade drawn.', libtcod.white)
	message('If this is your first time playing, press "?" for help.', libtcod.white)
	message('Collect souls to increase your power!', libtcod.white)
	#NPC DIAG TEST------------------------
	message(npc_name() + ': This is an NPC test message said by ' + npc_name())

def initialize_fov():
	global fov_recompute, fov_map
	fov_recompute = True

	#create the FOV map, according to the generated map
	fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			libtcod.map_set_properties(fov_map, x, y, not map[x][y].blocked, not map[x][y].block_sight)

	libtcod.console_clear(con)  #unexplored areas start black (which is the default background color)
	libtcod.console_set_fade(255, libtcod.black)

def play_game():
	global camera_x, camera_y

	player_action = None
	(camera_x, camera_y) = (0, 0)


	while not libtcod.console_is_window_closed():

		#handle keys and exit game if needed
		if player.fighter.tick == 0: #only do these things if it's the player's turn to move so there's not needless busy work

			#render the screen
			render_all()
			libtcod.console_flush()
			check_level_up()

			player_action = handle_keys()
			if player_action == 'exit':
				save_game()
				break
		else:
			player.fighter.tick = player.fighter.tick - 1

		#let monsters take their turn
		if game_state == 'playing' and player_action != 'didnt-take-turn':
			for object in objects:
				if object.ai:
					if object.fighter.tick == 0:
						object.ai.take_turn()
					else:
						object.fighter.tick = object.fighter.tick - 1

def main_menu():
	img = libtcod.image_load('menu_background.png')

	while not libtcod.console_is_window_closed():
		#show the background image, at twice the regular console resolution
		libtcod.image_set_key_color(img,libtcod.red)
		libtcod.image_blit_2x(img, 0, 0, 0, 1, 1, SCREEN_WIDTH, SCREEN_HEIGHT)
		libtcod.console_set_foreground_color(0, libtcod.light_yellow)
		libtcod.console_print_center(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_SET, 'POWERLORD')

		#show options and wait for the player's choice
		choice = menu('', ['New Game', 'Continue Saved Game', 'Quit'], 24)

		if choice == 0:  #new game
			fade_effect(FADE_COLOR_TRANSITION, 0)
			new_game()
			play_game()
		if choice == 1:  #load last game
			try:
				load_game()
			except:
				msgbox('\n No saved game to load.\n', 24)
				continue
			play_game()
		elif choice == 2:  #quit
			break

libtcod.console_set_custom_font('prestige12x12_gs_tc.png', libtcod.FONT_TYPE_GRAYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'POWERLORD', False)
libtcod.sys_set_fps(LIMIT_FPS)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
panel_bottom = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
panel_story = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

main_menu()
