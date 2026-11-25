import json
import math
import os
import random
import sys

import pygame

# --------------------------------------------------------------------------
# Cấu hình
# --------------------------------------------------------------------------
WIDTH, HEIGHT = 480, 640
FPS = 60

BLOCK = 32                       # 1 khối Minecraft trên màn hình (texture gốc 16x16, phóng 2x)
GROUND_ROWS = 2
GROUND_H = BLOCK * GROUND_ROWS
PLAY_H = HEIGHT - GROUND_H       # vùng chơi (trên mặt đất)
ROWS = PLAY_H // BLOCK           # số hàng khối trong vùng chơi

PIPE_W = BLOCK * 2
GAP_ROWS = 5                     # khe hở giữa 2 cột (tính theo khối)
PIPE_SPEED = 3
PIPE_SPACING = 240               # khoảng cách ngang giữa 2 cặp cột
MAX_GAP_SHIFT = 5                # lệch tối đa (số khối) giữa 2 khe liên tiếp

GRAVITY = 0.45
JUMP_VELOCITY = -8.0
MAX_FALL = 11.0

ANIMAL_SIZE = 48                 # kích thước vẽ con vật
HITBOX_SHRINK = 10               # hitbox nhỏ hơn hình một chút cho dễ chơi

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(BASE_DIR, "assets")
SAVE_FILE = os.path.join(BASE_DIR, "flappy_craft_save.json")

WHITE = (255, 255, 255)
SHADOW = (60, 60, 60)
GOLD = (252, 219, 60)


# --------------------------------------------------------------------------
# Pixel art vẽ bằng code
# --------------------------------------------------------------------------
STONE = [(125, 125, 125), (135, 135, 135), (115, 115, 115), (142, 142, 142)]
DIRT = [(134, 96, 67), (121, 85, 58), (145, 105, 75), (110, 77, 52)]
GRASS = [(95, 159, 53), (86, 148, 46), (104, 170, 60)]
MOSS = [(70, 110, 50), (85, 125, 60), (60, 95, 45)]


def shade_edges(tile):
    """Làm tối viền phải + dưới để nhìn ra từng khối."""
    n = tile.get_width()
    for i in range(n):
        for (x, y) in ((n - 1, i), (i, n - 1)):
            c = tile.get_at((x, y))
            tile.set_at((x, y), (int(c.r * 0.7), int(c.g * 0.7), int(c.b * 0.7)))
    return tile


def noise_tile(palette, seed):
    rnd = random.Random(seed)
    tile = pygame.Surface((16, 16))
    for y in range(16):
        for x in range(16):
            tile.set_at((x, y), rnd.choice(palette))
    return tile


def stone_tile(seed):
    tile = noise_tile(STONE, seed)
    rnd = random.Random(seed + 100)
    for _ in range(14):                       # vài vết nứt tối
        tile.set_at((rnd.randrange(16), rnd.randrange(16)), (88, 88, 88))
    return shade_edges(tile)


def mossy_tile(seed):
    tile = stone_tile(seed)
    rnd = random.Random(seed + 200)
    for y in range(15):
        for x in range(15):
            if rnd.random() < 0.45:
                tile.set_at((x, y), rnd.choice(MOSS))
    return shade_edges(tile)


def dirt_tile(seed=7):
    return shade_edges(noise_tile(DIRT, seed))


def grass_top_tile(seed=11):
    tile = noise_tile(DIRT, seed)
    rnd = random.Random(seed)
    for y in range(4):
        for x in range(16):
            tile.set_at((x, y), rnd.choice(GRASS))
    for x in range(16):                       # cỏ "rủ" xuống ở hàng thứ 5
        if rnd.random() < 0.5:
            tile.set_at((x, 4), rnd.choice(GRASS))
    return shade_edges(tile)


def to_block(tile16):
    return pygame.transform.scale(tile16, (BLOCK, BLOCK))


# Sprite 16x16 (nhìn nghiêng, quay mặt sang phải)
CHICKEN_GRID = [
    "................",
    "................",
    "..........WWWW..",
    "..........WWKW..",
    "..........WWWOO.",
    "..........WWWRR.",
    "..WW..WWWWWWW...",
    "..WWWWWWWWWWWW..",
    ".WWWwwWWWWWWWW..",
    "..WWwwwWWWWWWW..",
    "..WWWwwwWWWWWW..",
    "...WWWWWWWWWW...",
    "....WWWWWWWW....",
    ".......Y..Y.....",
    ".......Y..Y.....",
    "......YY.YY.....",
]
CHICKEN_PAL = {
    "W": (245, 245, 245), "w": (205, 205, 205), "K": (20, 20, 20),
    "O": (240, 140, 20), "R": (200, 30, 30), "Y": (235, 180, 30),
}

PIG_GRID = [
    "................",
    "................",
    "...........PP...",
    "..PPPPPPPPPPPP..",
    "..PPPPPPPPPPKP..",
    "..PPPPPPPPPPPPss",
    "..PPPPPPPPPPPPss",
    "..PPPPPPPPPPPP..",
    "..PPPppPPPPPPP..",
    "..PPPppPPPPPPP..",
    "..PPPPPPPPPPPP..",
    "...PPPPPPPPPP...",
    "..pp.pp...pp.pp.",
    "..pp.pp...pp.pp.",
    "..pp.pp...pp.pp.",
    "................",
]
PIG_PAL = {
    "P": (240, 160, 170), "p": (214, 120, 140), "K": (20, 20, 20), "s": (226, 118, 134),
}


def sprite_from_grid(grid, palette):
    surf = pygame.Surface((16, 16), pygame.SRCALPHA)
    for y, row in enumerate(grid):
        row = row.ljust(16, ".")[:16]
        for x, ch in enumerate(row):
            if ch in palette:
                surf.set_at((x, y), palette[ch])
    return pygame.transform.scale(surf, (ANIMAL_SIZE, ANIMAL_SIZE))


# --------------------------------------------------------------------------
# Tải asset (ưu tiên file của người dùng, thiếu thì dùng bản vẽ sẵn)
# --------------------------------------------------------------------------
def load_image(*parts):
    path = os.path.join(ASSET_DIR, *parts)
    if not os.path.isfile(path):
        return None
    try:
        return pygame.image.load(path).convert_alpha()
    except pygame.error:
        return None


def fit_scale(img, box):
    w, h = img.get_size()
    k = box / max(w, h)
    size = (max(1, round(w * k)), max(1, round(h * k)))
    if max(w, h) <= 64:                      # pixel art -> giữ nét
        return pygame.transform.scale(img, size)
    return pygame.transform.smoothscale(img, size)


class Assets:
    def __init__(self):
        # --- khối cột ---
        custom = load_image("pipe_block.png")
        custom_cap = load_image("pipe_cap.png")
        if custom:
            self.pipe_body = [pygame.transform.scale(custom, (BLOCK, BLOCK))]
        else:
            self.pipe_body = [to_block(stone_tile(s)) for s in (1, 2, 3, 4)]
        if custom_cap:
            self.pipe_cap = [pygame.transform.scale(custom_cap, (BLOCK, BLOCK))]
        elif custom:
            self.pipe_cap = self.pipe_body
        else:
            self.pipe_cap = [to_block(mossy_tile(s)) for s in (11, 12, 13)]

        # --- mặt đất ---
        top = load_image("ground_top.png")
        dirt = load_image("ground_dirt.png")
        self.ground_top = pygame.transform.scale(top, (BLOCK, BLOCK)) if top else to_block(grass_top_tile())
        self.ground_dirt = pygame.transform.scale(dirt, (BLOCK, BLOCK)) if dirt else to_block(dirt_tile())

        # --- nền ---
        self.bg_image = None
        bg = load_image("background.png")
        if bg:
            k = HEIGHT / bg.get_height()
            w = max(WIDTH, round(bg.get_width() * k))
            self.bg_image = pygame.transform.smoothscale(bg, (w, HEIGHT)).convert()
        self.sky = self._make_sky()
        self.hills = self._make_hills()
        self.cloud = self._make_cloud()
        self.sun = self._make_sun()

        # --- con vật ---
        self.animals = []                    # list[(tên, surface)]
        animal_dir = os.path.join(ASSET_DIR, "animals")
        if os.path.isdir(animal_dir):
            for fn in sorted(os.listdir(animal_dir)):
                if fn.lower().endswith((".png", ".webp", ".gif", ".jpg", ".jpeg")):
                    img = load_image("animals", fn)
                    if img:
                        self.animals.append((os.path.splitext(fn)[0], fit_scale(img, ANIMAL_SIZE)))
        self.animals.append(("Chicken", sprite_from_grid(CHICKEN_GRID, CHICKEN_PAL)))
        self.animals.append(("Pig", sprite_from_grid(PIG_GRID, PIG_PAL)))

        # --- font ---
        self.font_path = os.path.join(ASSET_DIR, "minecraft.ttf")
        if not os.path.isfile(self.font_path):
            self.font_path = None
        self._fonts = {}

    # ---- nền vẽ bằng code ----
    @staticmethod
    def _make_sky():
        sky = pygame.Surface((WIDTH, HEIGHT))
        top, bottom = (110, 165, 255), (195, 225, 255)
        for y in range(HEIGHT):
            t = y / HEIGHT
            c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
            pygame.draw.line(sky, c, (0, y), (WIDTH, y))
        return sky

    @staticmethod
    def _make_hills():
        """Đồi dạng khối, lặp liền mạch theo chiều ngang."""
        n = WIDTH // BLOCK
        surf = pygame.Surface((WIDTH, BLOCK * 8), pygame.SRCALPHA)
        for i in range(n):
            h = round(3 + 1.6 * math.sin(2 * math.pi * i / n) + 1.1 * math.sin(2 * math.pi * 3 * i / n + 1))
            h = max(1, min(7, h))
            x, y = i * BLOCK, surf.get_height() - h * BLOCK
            pygame.draw.rect(surf, (78, 138, 70), (x, y, BLOCK, h * BLOCK))
            pygame.draw.rect(surf, (96, 160, 82), (x, y, BLOCK, BLOCK // 2))
        return surf

    @staticmethod
    def _make_cloud():
        cloud = pygame.Surface((112, 48), pygame.SRCALPHA)
        for rect in ((16, 0, 64, 16), (0, 16, 112, 16), (16, 32, 80, 16)):
            pygame.draw.rect(cloud, (255, 255, 255, 235), rect)
        pygame.draw.rect(cloud, (225, 232, 245, 235), (16, 32, 80, 16))
        return cloud

    @staticmethod
    def _make_sun():
        sun = pygame.Surface((56, 56))
        sun.fill((255, 244, 140))
        pygame.draw.rect(sun, (255, 225, 60), (8, 8, 40, 40))
        return sun

    def font(self, size):
        if size not in self._fonts:
            if self.font_path:
                self._fonts[size] = pygame.font.Font(self.font_path, size)
            else:
                self._fonts[size] = pygame.font.SysFont("menlo,consolas,couriernew,monospace", size, bold=True)
        return self._fonts[size]


# --------------------------------------------------------------------------
# Đối tượng game
# --------------------------------------------------------------------------
class Bird:
    def __init__(self, sprite):
        self.sprite = sprite
        self.x = WIDTH // 4
        self.y = PLAY_H // 2
        self.vel = 0.0

    def flap(self):
        self.vel = JUMP_VELOCITY

    def update(self):
        self.vel = min(self.vel + GRAVITY, MAX_FALL)
        self.y += self.vel

    def hitbox(self):
        size = ANIMAL_SIZE - HITBOX_SHRINK
        r = pygame.Rect(0, 0, size, size)
        r.center = (int(self.x), int(self.y))
        return r

    def draw(self, surf):
        angle = max(-70, min(25, -self.vel * 4))      # ngước lên khi bay, chúi xuống khi rơi
        img = pygame.transform.rotate(self.sprite, angle)
        surf.blit(img, img.get_rect(center=(int(self.x), int(self.y))))


class Pipe:
    def __init__(self, x, top_rows, body_tiles, cap_tiles):
        self.x = float(x)
        self.top_rows = top_rows
        self.bottom_rows = ROWS - GAP_ROWS - top_rows
        self.passed = False
        self.top_surf = self._build(self.top_rows, body_tiles, cap_tiles, cap_last=True)
        self.bottom_surf = self._build(self.bottom_rows, body_tiles, cap_tiles, cap_last=False)

    @staticmethod
    def _build(rows, body_tiles, cap_tiles, cap_last):
        surf = pygame.Surface((PIPE_W, rows * BLOCK), pygame.SRCALPHA)
        for r in range(rows):
            is_cap = (r == rows - 1) if cap_last else (r == 0)
            for c in range(PIPE_W // BLOCK):
                tile = random.choice(cap_tiles if is_cap else body_tiles)
                surf.blit(tile, (c * BLOCK, r * BLOCK))
        return surf

    def update(self):
        self.x -= PIPE_SPEED

    def rects(self):
        x = int(self.x)
        return (
            pygame.Rect(x, 0, PIPE_W, self.top_rows * BLOCK),
            pygame.Rect(x, (self.top_rows + GAP_ROWS) * BLOCK, PIPE_W, self.bottom_rows * BLOCK),
        )

    def draw(self, surf):
        top, bottom = self.rects()
        surf.blit(self.top_surf, top.topleft)
        surf.blit(self.bottom_surf, bottom.topleft)


# --------------------------------------------------------------------------
# Game
# --------------------------------------------------------------------------
def load_best():
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            return int(json.load(f).get("best", 0))
    except (OSError, ValueError, TypeError):
        return 0


def save_best(best):
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump({"best": best}, f)
    except OSError:
        pass


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Flappy Craft")
        self.clock = pygame.time.Clock()
        self.assets = Assets()
        self.best = load_best()
        self.animal_idx = 0
        self.state = "menu"                  # menu | play | dead
        self.clouds = [[random.uniform(0, WIDTH), y, random.uniform(0.25, 0.6)] for y in (60, 150, 240)]
        self.t = 0
        self.reset()

    # ---- trạng thái ----
    def reset(self):
        self.bird = Bird(self.assets.animals[self.animal_idx][1])
        self.pipes = []
        self.score = 0
        self.flash = 0
        self.dead_timer = 0
        self.new_best = False
        self.ground_x = 0.0
        self.hill_x = 0.0
        self.bg_x = 0.0
        self.last_top_rows = None

    def change_animal(self, step):
        self.animal_idx = (self.animal_idx + step) % len(self.assets.animals)
        self.bird.sprite = self.assets.animals[self.animal_idx][1]

    def action(self):
        if self.state == "menu":
            self.state = "play"
            self.bird.flap()
        elif self.state == "play":
            self.bird.flap()
        elif self.state == "dead" and self.dead_timer > 30:
            self.state = "menu"
            self.reset()

    def die(self):
        if self.state != "play":
            return
        self.state = "dead"
        self.dead_timer = 0
        self.flash = 8
        if self.score > self.best:
            self.best = self.score
            self.new_best = True
            save_best(self.best)

    # ---- cập nhật ----
    def spawn_pipe(self):
        lo, hi = 2, ROWS - GAP_ROWS - 2
        if self.last_top_rows is not None:
            lo = max(lo, self.last_top_rows - MAX_GAP_SHIFT)
            hi = min(hi, self.last_top_rows + MAX_GAP_SHIFT)
        top_rows = random.randint(lo, hi)
        self.last_top_rows = top_rows
        self.pipes.append(Pipe(WIDTH, top_rows, self.assets.pipe_body, self.assets.pipe_cap))

    def scroll(self):
        self.ground_x = (self.ground_x + PIPE_SPEED) % BLOCK
        self.hill_x = (self.hill_x + PIPE_SPEED * 0.4) % WIDTH
        if self.assets.bg_image:
            self.bg_x = (self.bg_x + PIPE_SPEED * 0.3) % self.assets.bg_image.get_width()

    def update(self):
        self.t += 1
        for c in self.clouds:                # mây luôn trôi
            c[0] -= c[2]
            if c[0] < -120:
                c[0] = WIDTH + random.uniform(0, 80)

        if self.state != "dead":
            self.scroll()

        if self.state == "menu":
            self.bird.y = PLAY_H // 2 + math.sin(self.t * 0.08) * 8

        elif self.state == "play":
            self.bird.update()
            hb = self.bird.hitbox()
            if hb.top < 0:                   # chạm trần: bị chặn lại, không chết
                self.bird.y -= hb.top
                self.bird.vel = 0
                hb = self.bird.hitbox()
            if hb.bottom >= PLAY_H:          # chạm đất
                self.bird.y -= hb.bottom - PLAY_H
                self.die()
                return

            if not self.pipes or self.pipes[-1].x <= WIDTH - PIPE_SPACING:
                self.spawn_pipe()
            for pipe in self.pipes:
                pipe.update()
                if not pipe.passed and pipe.x + PIPE_W < self.bird.x:
                    pipe.passed = True
                    self.score += 1
                if any(hb.colliderect(r) for r in pipe.rects()):
                    self.die()
            self.pipes = [p for p in self.pipes if p.x + PIPE_W > 0]

        elif self.state == "dead":
            self.dead_timer += 1
            self.flash = max(0, self.flash - 1)
            self.bird.update()
            hb = self.bird.hitbox()
            if hb.bottom >= PLAY_H:
                self.bird.y -= hb.bottom - PLAY_H
                self.bird.vel = 0

    # ---- vẽ ----
    def text(self, msg, size, center, color=WHITE):
        font = self.assets.font(size)
        shadow = font.render(msg, True, SHADOW)
        main = font.render(msg, True, color)
        rect = main.get_rect(center=center)
        self.screen.blit(shadow, rect.move(3, 3))
        self.screen.blit(main, rect)

    def panel(self, rect):
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        s.fill((0, 0, 0, 200))
        self.screen.blit(s, rect.topleft)
        pygame.draw.rect(self.screen, (200, 200, 200), rect, 2)

    def draw_background(self):
        a = self.assets
        if a.bg_image:
            w = a.bg_image.get_width()
            x = -int(self.bg_x)
            self.screen.blit(a.bg_image, (x, 0))
            if x + w < WIDTH:
                self.screen.blit(a.bg_image, (x + w, 0))
            return
        self.screen.blit(a.sky, (0, 0))
        self.screen.blit(a.sun, (WIDTH - 110, 50))
        for x, y, _ in self.clouds:
            self.screen.blit(a.cloud, (int(x), y))
        hx = -int(self.hill_x)
        hy = PLAY_H - a.hills.get_height()
        self.screen.blit(a.hills, (hx, hy))
        self.screen.blit(a.hills, (hx + WIDTH, hy))

    def draw_ground(self):
        a = self.assets
        gx = -int(self.ground_x)
        for i in range(WIDTH // BLOCK + 2):
            x = gx + i * BLOCK
            self.screen.blit(a.ground_top, (x, PLAY_H))
            for r in range(1, GROUND_ROWS):
                self.screen.blit(a.ground_dirt, (x, PLAY_H + r * BLOCK))

    def draw(self):
        self.draw_background()
        for pipe in self.pipes:
            pipe.draw(self.screen)
        self.bird.draw(self.screen)
        self.draw_ground()

        if self.state == "menu":
            self.text("FLAPPY CRAFT", 52, (WIDTH // 2, 120), GOLD)
            name = self.assets.animals[self.animal_idx][0]
            self.text(f"<  {name}  >", 28, (WIDTH // 2, PLAY_H // 2 + 70))
            self.text("SPACE / CLICK to start", 22, (WIDTH // 2, PLAY_H - 90))
            self.text("LEFT / RIGHT: choose animal", 18, (WIDTH // 2, PLAY_H - 60))
            self.text(f"Best: {self.best}", 22, (WIDTH // 2, 190))
        elif self.state == "play":
            self.text(str(self.score), 64, (WIDTH // 2, 70))
        else:
            self.text(str(self.score), 64, (WIDTH // 2, 70))
            box = pygame.Rect(0, 0, 340, 210)
            box.center = (WIDTH // 2, PLAY_H // 2 - 20)
            self.panel(box)
            self.text("GAME OVER", 40, (box.centerx, box.top + 45), (230, 70, 60))
            self.text(f"Score: {self.score}", 26, (box.centerx, box.top + 95))
            best_color = GOLD if self.new_best else WHITE
            label = "NEW BEST!  " if self.new_best else "Best: "
            self.text(f"{label}{self.best}", 26, (box.centerx, box.top + 130), best_color)
            if self.dead_timer > 30:
                self.text("SPACE / CLICK to continue", 18, (box.centerx, box.top + 175))

        if self.flash > 0:
            overlay = pygame.Surface((WIDTH, HEIGHT))
            overlay.fill(WHITE)
            overlay.set_alpha(self.flash * 28)
            self.screen.blit(overlay, (0, 0))

    # ---- vòng lặp ----
    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return False
                if e.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    self.action()
                elif self.state == "menu" and e.key in (pygame.K_LEFT, pygame.K_a):
                    self.change_animal(-1)
                elif self.state == "menu" and e.key in (pygame.K_RIGHT, pygame.K_d):
                    self.change_animal(1)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.action()
        return True

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    pygame.init()
    Game().run()
