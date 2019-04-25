from trezor import config, wire
from trezor.messages.Success import Success
from trezor.pin import pin_to_int
from trezor.ui.text import Text

from apps.common import storage
from apps.common.confirm import require_confirm
from apps.common.mnemonic import bip39


async def load_device(ctx, msg):
    # TODO implement SLIP-39
    if storage.is_initialized():
        raise wire.UnexpectedMessage("Already initialized")

    if msg.node is not None:
        raise wire.ProcessError("LoadDevice.node is not supported")

    words = msg.mnemonic.split(" ")
    if not msg.skip_checksum and not bip39.check(msg.mnemonic):
        raise wire.ProcessError("Mnemonic is not valid")

    text = Text("Loading seed")
    text.bold("Loading private seed", "is not recommended.")
    text.normal("Continue only if you", "know what you are doing!")
    await require_confirm(ctx, text)

    secret = bip39.process_all([words])
    storage.store_mnemonic(
        secret=secret,
        mnemonic_type=bip39.get_type(),
        needs_backup=True,
        no_backup=False,
    )
    storage.load_settings(use_passphrase=msg.passphrase_protection, label=msg.label)
    if msg.pin:
        config.change_pin(pin_to_int(""), pin_to_int(msg.pin))

    return Success(message="Device loaded")
