import json
import math
import random
from copy import copy
import pygame

FRAME_RATE = 30

RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
BLACK = (0, 0, 0)
GREY = (100, 100, 100)

GAME_FIRST_HIT = 'first hit'
GAME_LAST_STANDING = 'last standing'
DIRECTION_LEFT = -1
DIRECTION_RIGHT = 1
MOVE_DISTANCE = 20


def eq(x, y, a, b, c, d):
    return (x - a) / (c - a) - (y - b) / (d - b)


class ShootOption:
    LINEAR = 0
    QUAD = 1
    LOG = 2
    SIN = 3

    def __init__(self):
        self.a = 0.0
        self.b = 0.0
        self.c = 0.0
        self.speed = 1
        self.mode = self.LINEAR

    def next_mode(self):
        if self.mode < self.SIN:
            self.mode += 1
        else:
            self.mode = 0

    def __str__(self):
        if self.mode == self.LINEAR:
            return 'direct (y = ax + b)'
        elif self.mode == self.QUAD:
            return 'high trajectory (y = ax^2 + bx + c)'
        elif self.mode == self.LOG:
            return 'armament (y = a*log(b, x)'
        else:
            return 'crazy ship (y = a*sin(b*x))'

    def update(self, x):
        if self.mode == self.LINEAR:
            return self.a * x + self.b
        elif self.mode == self.QUAD:
            return self.a * x ** 2 + self.b * x + self.c
        elif self.mode == self.LOG:
            try:
                return self.a * math.log(x, self.b)
            except:
                return x
        else:
            return self.a * math.sin(self.b * x)


def get_ground_y(ground, x):
    l, r = get_ground_points(ground, x)
    return ((r[1] - l[1])*(x - l[0])/(r[0] - l[0])) + l[1]


class Tank(object):
    def __init__(self, x, y, color=RED, options=None):
        self.settings = options if options is not None else {}
        self.x = x
        self.y = y
        self.color = color
        self.active = False
        self.alive = True
        self.shoot_option = ShootOption()
        self.hits = 0
        self.shoot_paths = []
        self.moves_left = 5

    def explode(self):
        self.alive = False

    def draw(self, surface):
        if self.active:
            pygame.draw.circle(surface, BLACK,
                               map(int, (self.x, self.y)), 10)

        for line in self.shoot_paths:
            pygame.draw.lines(surface, GREY, False, line)

        pygame.draw.circle(surface, self.color if self.alive else BLACK,
                           map(int, (self.x, self.y)), 7)

    def move(self, direction, ground):
        if self.moves_left == 0:
            return

        new_x = self.x + direction * MOVE_DISTANCE
        new_y = get_ground_y(ground, new_x)
        self.x = new_x
        self.y = new_y
        self.moves_left -= 1

    def create_shooting_path(self):
        line = []
        if self.shoot_option.speed > 0:
            l = 0
            r = 1024 - self.x
        else:
            l = -self.x
            r = 0
        for x in range(l, r):
            y = self.shoot_option.update(x)
            line.append((self.x + x, self.y + y))
        return line

    def shoot(self):
        self.moves_left = 5
        line = self.create_shooting_path()
        self.shoot_paths.append(line)
        return Bullet(self.x, self.y - 3, copy(self.shoot_option), self.settings)

    def check_for_dead(self):
        return self.hits <= self.settings['number_of_hits']


def get_ground_points(ground, x):
    l = None
    r = None
    for i, point in enumerate(ground):
        if point[0] > x:
            r = point
            l = ground[i - 1]
            break
    return l, r


class Bullet(object):
    def __init__(self, x, y, shoot_option, options):
        self.options = options
        self.start_x = x
        self.x = 0
        self.y = y
        self.start_time = options['injury_radius'] + 1
        self.start_y = y
        self.shoot_option = shoot_option

    def update(self):
        if self.start_time > 0:
            self.start_time -= 1
        self.x += self.shoot_option.speed
        self.y = self.shoot_option.update(self.x)

    def draw(self, surface):
        pygame.draw.circle(surface, (255, 255, 255), (int(self.x + self.start_x), int(self.y + self.start_y)), 3)

    def collides_with(self, tank):
        x = self.x + self.start_x
        y = self.y + self.start_y
        distance = math.hypot(x - tank.x, y - tank.y)
        return distance < self.options['injury_radius'] and self.start_time == 0

    def is_collides_with_ground(self, ground):
        l, r = get_ground_points(ground, self.x)

        try:
            a = eq(self.x + self.start_x, self.start_y + self.y, *(l + r))
            b = eq(self.x + self.start_x, 600, *(l + r))
        except ZeroDivisionError:
            return False
        return a * b > 0

    def is_on_screen(self):
        return 0 < self.x + self.start_x < 1024 and 0 < self.y + self.start_y < 600


class Game(object):
    def __init__(self, options):
        self.options = options
        self.players = options['players']
        land = [random.randrange(300 - 100, 300 + 100) for _ in range(self.players)]
        colors = [RED, GREEN, BLUE, YELLOW]
        random.shuffle(colors)

        self.tanks = []
        self.ground = [(0, 300)]

        x_step = 1024 / len(land)
        x = 200
        for i, y in enumerate(land):
            tank = Tank(x, y, color=colors[i], options=self.options)
            self.tanks.append(tank)

            self.ground.append((x, y))
            x += x_step

        self.ground.append((1024, 300))

        self.bullets = []
        self.current_tank = self.tanks[0]
        self.over = False

        self.font = pygame.font.Font(None, 24)

    def handle_events(self, events, state_manager):
        for event in events:
            if event.type == pygame.QUIT:
                return
            elif event.type == pygame.KEYDOWN:
                if event.unicode in (u'q', u'Q'):
                    self.game_over()
                if event.unicode in (u'n', u'N'):
                    state_manager.go('game')
                if event.key == pygame.K_SPACE and not self.over:
                    self.shoot()

                if not self.over:
                    current_tank = self.current_tank

                    shift = pygame.key.get_mods() & pygame.KMOD_SHIFT
                    if event.key == pygame.K_a:
                        if shift:
                            current_tank.shoot_option.a -= 0.1
                        else:
                            current_tank.shoot_option.a += 0.1
                    if event.key == pygame.K_LEFT:
                        current_tank.move(DIRECTION_LEFT, self.ground)
                    if event.key == pygame.K_RIGHT:
                        current_tank.move(DIRECTION_RIGHT, self.ground)
                    if event.key == pygame.K_b:
                        if shift:
                            current_tank.shoot_option.b -= 0.1
                        else:
                            current_tank.shoot_option.b += 0.1
                    if event.key == pygame.K_c:
                        if shift:
                            current_tank.shoot_option.c -= 0.1
                        else:
                            current_tank.shoot_option.c += 0.1
                    if event.key == pygame.K_m:
                        current_tank.shoot_option.next_mode()
                    if event.key == pygame.K_s:
                        if shift:
                            current_tank.shoot_option.speed -= 1
                            if current_tank.shoot_option.speed == 0:
                                current_tank.shoot_option.speed = -1
                        else:
                            current_tank.shoot_option.speed += 1
                            if current_tank.shoot_option.speed == 0:
                                current_tank.shoot_option.speed = 1

    def draw(self, screen):
        screen.fill((0, 0, 64))
        pygame.draw.polygon(screen, (0, 120, 0),
                            self.ground + [(screen.get_width(), screen.get_height()), (0, screen.get_height())])
        for tank in self.tanks:
            tank.active = tank is self.current_tank
            tank.draw(screen)
        for bullet in self.bullets:
            bullet.draw(screen)

        mode = str(self.current_tank.shoot_option)
        mode_str = self.font.render(mode, True, self.current_tank.color)
        screen.blit(mode_str, (20, 20))
        pos = [20, 40]
        options = self.current_tank.shoot_option
        for name, value in [("a", options.a), ("b", options.b), ("c", options.c), ("speed", options.speed)]:
            mode_str = self.font.render("{0}: {1:.1f}".format(name, value), True, self.current_tank.color)
            screen.blit(mode_str, tuple(pos))
            pos[1] += 20

    def update(self):
        live_bullets = []
        for bullet in self.bullets:
            bullet.update()
            if not bullet.is_on_screen():
                continue
            hit = False
            for tank in self.tanks:
                if bullet.collides_with(tank):
                    if tank.check_for_dead():
                        tank.explode()
                        if self.current_tank == tank:
                            self.next_tank()

                    hit = True

                    if self.check_is_over():
                        self.game_over()

                    break
            if hit:
                continue
            if bullet.is_collides_with_ground(self.ground):
                continue
            live_bullets.append(bullet)
        self.bullets = live_bullets

    def shoot(self):
        self.bullets.append(self.current_tank.shoot())
        # hardcoded for two tanks
        self.next_tank()

    def next_tank(self):
        self.current_tank = self.tanks[(self.tanks.index(self.current_tank) + 1) % len(self.tanks)]

    def check_is_over(self):
        if self.options['game_type'] == GAME_FIRST_HIT:
            return True

        alive = 0
        if self.options['game_type'] == GAME_LAST_STANDING:
            for tank in self.tanks:
                if tank.alive:
                    alive += 1

            return alive == 1

    def game_over(self):
        exit(0)


class Menu(object):
    def __init__(self, options):
        self.font = pygame.font.Font(None, 48)
        self.small_font = pygame.font.Font(None, 32)
        self.font_color = (255, 255, 255)
        self.start_game_rect = None
        self.options_rect = None
        self.exit_rect = None
        self.how_to_rect = None
        self.players = 2
        self.options = options

    def draw(self, screen):
        screen.fill((0, 0, 64))

        self.start_game_rect = draw_text(self.font, screen, "Start Game", (512, 100), self.font_color)
        draw_text(self.small_font,
                  screen,
                  "Players: {0} (press Up/Down to change)".format(self.players),
                  (512, 125),
                  self.font_color)
        self.how_to_rect = draw_text(self.font, screen, "How to play", (512, 200), self.font_color)
        self.options_rect = draw_text(self.font, screen, "Options", (512, 300), self.font_color)
        self.exit_rect = draw_text(self.font, screen, "Exit", (512, 400), self.font_color)

    def handle_events(self, events, state_manager):
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if self.start_game_rect.collidepoint(*pos):
                    self.options['players'] = self.players
                    state_manager.go('game', self.options)
                if self.options_rect.collidepoint(*pos):
                    state_manager.go('options', self.options)
                if self.how_to_rect.collidepoint(*pos):
                    state_manager.go('how_to', self.options)
                if self.exit_rect.collidepoint(*pos):
                    exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    if self.players < 4:
                        self.players += 1
                elif event.key == pygame.K_DOWN:
                    if self.players > 2:
                        self.players -= 1

    def update(self):
        pass


def draw_text(font, screen, string, pos, color):
    text = font.render(string, True, color)
    text_rect = text.get_rect(center=pos)
    screen.blit(text, text_rect)
    return text_rect


class Options(object):
    def __init__(self, settings):
        self.settings = settings
        self.keys = settings.keys()
        self.font = pygame.font.Font(None, 48)
        self.small_font = pygame.font.Font(None, 32)
        self.font_color = (255, 255, 255)
        self.current_setting = self.keys[0]

    def draw(self, screen):
        screen.fill((0, 0, 64))

        draw_text(self.small_font, screen,
                  'Press Up/Down to choose option and Left/Right to change it, Esc - back to main menu',
                  (512, 100), self.font_color)

        y = 140
        for key in self.keys:
            self.draw_option(screen, key, y)
            y += 40

    def draw_option(self, screen, key, y):
        draw_text(self.font, screen,
                  '{1} {2}: {0}'.format(
                      self.settings[key],
                      '*' if self.current_setting == key else '',
                      key.replace('_', ' ')),
                  (512, y), self.font_color)

    def handle_events(self, events, state_manager):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.settings['test'] = 1
                    state_manager.go('menu', self.settings)
                    return
                if event.key == pygame.K_DOWN:
                    if self.current_setting != self.keys[-1]:
                        self.current_setting = self.keys[self.keys.index(self.current_setting) + 1]
                if event.key == pygame.K_UP:
                    if self.current_setting != self.keys[0]:
                        self.current_setting = self.keys[self.keys.index(self.current_setting) - 1]
                if event.key == pygame.K_LEFT:
                    self.change_option(-1)
                if event.key == pygame.K_RIGHT:
                    self.change_option(1)

    def update(self):
        pass

    def change_option(self, left_or_right):
        if self.current_setting == 'injury_radius':
            self.settings['injury_radius'] += 10 * left_or_right
            if self.settings['injury_radius'] < 10:
                self.settings['injury_radius'] = 10
        if self.current_setting == 'game_type':
            if self.settings['game_type'] == GAME_FIRST_HIT:
                self.settings['game_type'] = GAME_LAST_STANDING
            else:
                self.settings['game_type'] = GAME_FIRST_HIT
        if self.current_setting == 'number_of_hits':
            if left_or_right == -1 and self.settings['number_of_hits'] > 1:
                self.settings['number_of_hits'] += left_or_right
            elif left_or_right == 1:
                self.settings['number_of_hits'] += left_or_right
        if self.current_setting == 'random_power_ups':
            self.settings['random_power_ups'] = not self.settings['random_power_ups']


class HowToScreen(object):
    def __init__(self, _):
        self.font = pygame.font.Font(None, 48)
        self.small_font = pygame.font.Font(None, 32)
        self.font_color = (255, 255, 255)
        self.text = """
M - change shooting mode
A / Shift + A - change 'a' coefficient
B / Shift + B - change 'b' coefficient
C / Shift + C - change 'c' coefficient
S / Shift + S - change speed of the rocket
Left Arrow - move tank left
Right Arrow - move tank right
Q - quit
N - new game
"""

    def draw(self, screen):
        draw_text(self.font, screen, 'Keyboard shortcuts', (512, 100), self.font_color)

        y = 120
        for line in self.text.splitlines(False):
            draw_text(self.small_font, screen, line, (512, y), self.font_color)
            y += 25

    @staticmethod
    def handle_events(events, state_manager):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    state_manager.go('menu')
                    return

    def update(self):
        pass


class StateManager(object):
    def __init__(self, states, current, settings):
        self.settings = settings
        self.states = states
        self.current = states[current](settings)

    def go(self, state, settings=None):
        if settings is None:
            settings = self.settings
        self.current = self.states[state](settings)


def main():
    pygame.init()
    pygame.display.set_caption('Py Scorched Earth')

    screen = pygame.display.set_mode((1024, 600))
    clock = pygame.time.Clock()

    default_settings = {
        "injury_radius": 40,
        "game_type": 'first hit',
        "number_of_hits": 3,
        "random_power_ups": False
    }

    state_manager = StateManager({
        'game': Game,
        'menu': Menu,
        'options': Options,
        'how_to': HowToScreen
    },
        'menu',
        default_settings)

    pygame.key.set_repeat(200, 20)

    while True:
        scene = state_manager.current
        # draw
        screen.fill((0, 0, 64))
        scene.draw(screen)
        pygame.display.flip()
        scene.handle_events(pygame.event.get(), state_manager)
        # move
        scene.update()
        # wait
        clock.tick(FRAME_RATE)


if __name__ == '__main__':
    main()
    exit(0)
