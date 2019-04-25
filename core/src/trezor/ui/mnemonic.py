from trezor import io, loop, res, ui
from trezor.crypto import bip39, slip39
from trezor.ui import display
from trezor.ui.button import BTN_CLICKED, ICON, Button

if __debug__:
    from apps.debug import input_signal

MNEMONIC_KEYS = ("ab", "cd", "ef", "ghij", "klm", "nopq", "rs", "tuv", "wxyz")


def key_buttons(keys):
    return [Button(ui.grid(i + 3, n_y=4), k) for i, k in enumerate(keys)]


def compute_mask(text: str) -> int:
    mask = 0
    for c in text:
        shift = ord(c) - 97  # ord('a') == 97
        if shift < 0:
            continue
        mask |= 1 << shift
    return mask


class Input(Button):
    def __init__(self, area: tuple, content: str = "", word: str = ""):
        super().__init__(area, content)
        self.word = word
        self.icon = None
        self.pending = False

    def edit(self, content: str, word: str, pending: bool):
        if len(content) > 3:
            content = word
        self.word = word
        self.content = content
        self.pending = pending
        self.taint()
        if content == word:  # confirm button
            self.enable()
            self.normal_style = ui.BTN_KEY_CONFIRM["normal"]
            self.active_style = ui.BTN_KEY_CONFIRM["active"]
            self.icon = ui.ICON_CONFIRM
        elif word:  # auto-complete button
            self.enable()
            self.normal_style = ui.BTN_KEY["normal"]
            self.active_style = ui.BTN_KEY["active"]
            self.icon = ui.ICON_CLICK
        else:  # disabled button
            self.disable()
            self.icon = None

    def render_content(self, s, ax, ay, aw, ah):
        text_style = s["text-style"]
        fg_color = s["fg-color"]
        bg_color = s["bg-color"]

        if len(self.content) > 3:
            self.content = self.word

        t = self.content  # input content
        i = self.icon  # rendered icon
        w = self.word[len(t) :]  # suggested word

        tx = ax + 24  # x-offset of the content
        ty = ay + ah // 2 + 8  # y-offset of the content

        # input content and the suggested word
        display.text(tx, ty, t, text_style, fg_color, bg_color)
        width = display.text_width(t, text_style)
        display.text(tx + width, ty, w, text_style, ui.GREY, bg_color)

        # p = self.pending
        if len(t) < 4:  # pending marker
            pw = display.text_width(t, text_style)
            px = tx + width - pw
            display.bar(px, ty + 2, pw + 1, 3, fg_color)

        if i:  # icon
            ix = ax + aw - ICON * 2
            iy = ty - ICON
            display.icon(ix, iy, res.load(i), fg_color, bg_color)


class MnemonicKeyboard(ui.Widget):
    def __init__(self, prompt: str = ""):
        self.prompt = prompt
        self.input = Input(ui.grid(1, n_x=4, n_y=4, cells_x=3), "", "")
        self.input_content = ""
        self.back = Button(
            ui.grid(0, n_x=4, n_y=4), res.load(ui.ICON_BACK), style=ui.BTN_CLEAR
        )
        self.keys = key_buttons(MNEMONIC_KEYS)
        self.pbutton = None  # pending key button
        self.pindex = 0  # index of current pending char in pbutton

    def taint(self):
        super().taint()
        self.input.taint()
        self.back.taint()
        for btn in self.keys:
            btn.taint()

    def render(self):
        if self.input.content:
            self.input.content = self.input_content
            # content button and backspace
            self.input.render()
            self.back.render()
        else:
            # prompt
            display.bar(0, 8, ui.WIDTH, 60, ui.BG)
            display.text(20, 40, self.prompt, ui.BOLD, ui.GREY, ui.BG)
        # key buttons
        for btn in self.keys:
            btn.render()

    def touch(self, event, pos):
        content = self.input.content
        word = self.input.word

        if self.back.touch(event, pos) == BTN_CLICKED:
            # backspace, delete the last character of input
            self.edit(self.input_content[:-1])
            return

        if self.input.touch(event, pos) == BTN_CLICKED:
            # input press, either auto-complete or confirm
            if content == "":
                return
            elif (word and content == word) or len(content) > 3:
                self.edit("")
                return word
            else:
                self.edit(word)
                return

        for btn in self.keys:
            if btn.touch(event, pos) == BTN_CLICKED:
                # key press, add new char to input or cycle the pending button
                if self.pbutton is btn:
                    index = (self.pindex + 1) % len(btn.content)
                    self.input_content += content[:-1] + btn.content[index]
                else:
                    index = 0
                    self.input_content += btn.content[0]
                self.edit(self.input_content)
                return

    def edit(self, content, button=None, index=0):
        word = slip39.find_word(content, False) or ""
        mask = slip39.complete_word(content, False)

        self.pbutton = button
        self.pindex = index
        self.input_content = word[:len(content)]
        self.input.edit(content, word, button is not None)

        # enable or disable key buttons
        if len(content) > 3:
            mask = 0
        for btn in self.keys:
            if btn is button or compute_mask(btn.content) & mask:
                btn.enable()
            else:
                btn.disable()

    async def __iter__(self):
        if __debug__:
            return await loop.spawn(self.edit_loop(), input_signal)
        else:
            return await self.edit_loop()

    async def edit_loop(self):
        touch = loop.wait(io.TOUCH)
        wait_touch = loop.spawn(touch)
        content = None

        self.back.taint()
        self.input.taint()

        while content is None:
            self.render()
            wait = wait_touch
            result = await wait
            if touch in wait.finished:
                event, *pos = result
                content = self.touch(event, pos)
        return content
