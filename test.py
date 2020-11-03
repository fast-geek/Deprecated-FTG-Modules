import logging
import time

from io import BytesIO

from .. import loader, utils
from time import sleep
from datetime import datetime

logger = logging.getLogger(__name__)


@loader.test(args=None)
async def dumptest(conv):
    m = await conv.send_message("test")
    await conv.send_message(".dump", reply_to=m)
    r = await conv.get_response()
    assert r.message.startswith("Message(") and "test" in r.message, r


@loader.test(args=("0", "FORCE_INSECURE"))
async def logstest(conv):
    r = await conv.get_response()
    assert r.message == "Loading media...", r
    r2 = await conv.get_response()
    assert r2.document, r2


@loader.tds
class TestMod(loader.Module):
    """Self-tests"""
    strings = {"name": "Tester",
               "pong": "Pong",
               "bad_loglevel": ("<b>Invalid loglevel. Please refer to </b>"
                                "<a href='https://docs.python.org/3/library/logging.html#logging-levels'>"
                                "the docs</a><b>.</b>"),
               "set_loglevel": "<b>Please specify verbosity as an integer or string</b>",
               "uploading_logs": "<b>Uploading logs...</b>",
               "no_logs": "<b>You don't have any logs at verbosity {}.</b>",
               "logs_filename": "ftg-logs.txt",
               "logs_caption": "friendly-telegram logs with verbosity {}",
               "logs_unsafe": ("<b>Warning: running this command may reveal personal or dangerous information. "
                               "You can write</b> <code>{}</code> <b>at the end to accept the risks</b>"),
               "logs_force": "FORCE_INSECURE",
               "suspend_invalid_time": "<b>Invalid time to suspend</b>"}

    @loader.test(resp="Pong")
    @loader.unrestricted
    async def pingcmd(self, message):
        """Does nothing"""
        start = datetime.now()
        await utils.answer(message, self.strings("`Ping checking...`", message))
        end = datetime.now()
        ms = (end - start).microseconds / 1000
        sleep(0.5)
        await utils.answer(message, self.strings("**Ping:** `{}ms`".format(ms), message))

    @loader.test(func=dumptest)
    async def dumpcmd(self, message):
        """Use in reply to get a dump of a message"""
        if not message.is_reply:
            return
        await utils.answer(message, "<code>"
                           + utils.escape_html((await message.get_reply_message()).stringify()) + "</code>")

    @loader.test(func=logstest)
    async def logscmd(self, message):
        """.logs <level>
           Dumps logs. Loglevels below WARNING may contain personal info."""
        args = utils.get_args(message)
        if not len(args) == 1 and not len(args) == 2:
            await utils.answer(message, self.strings("set_loglevel", message))
            return
        try:
            lvl = int(args[0])
        except ValueError:
            # It's not an int. Maybe it's a loglevel
            lvl = getattr(logging, args[0].upper(), None)
        if not isinstance(lvl, int):
            await utils.answer(message, self.strings("bad_loglevel", message))
            return
        if not (lvl >= logging.WARNING or (len(args) == 2 and args[1] == self.strings("logs_force", message))):
            await utils.answer(message,
                               self.strings("logs_unsafe", message).format(utils.escape_html(self.strings("logs_force",
                                                                                                          message))))
            return
        [handler] = logging.getLogger().handlers
        logs = ("\n".join(handler.dumps(lvl))).encode("utf-16")
        if not len(logs) > 0:
            await utils.answer(message, self.strings("no_logs", message).format(lvl))
            return
        logs = BytesIO(logs)
        logs.name = self.strings("logs_filename", message)
        await utils.answer(message, logs, caption=self.strings("logs_caption", message).format(lvl))

    @loader.owner
    async def suspendcmd(self, message):
        """.suspend <time>
           Suspends the bot for N seconds"""
        # Blocks asyncio event loop, preventing ANYTHING happening (except multithread ops,
        # but they will be blocked on return).
        try:
            time.sleep(int(utils.get_args_raw(message)))
        except ValueError:
            await utils.answer(message, self.strings("suspend_invalid_time", message))

    async def client_ready(self, client, db):
        self.client = client
