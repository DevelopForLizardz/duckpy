#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
duck.py: Core module behind duckpy's functionality.
"""

import sys
import os
import time
import logging
import argparse
import pyautogui


# Enable or disable pyautogui failsafes, depending on target/ whether or
# not we are hardcore quacking
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

# Setup logging
LOG_LEVEL_DEFAULT = logging.WARNING  # default
LOG_FORMAT = "%(name)s - %(asctime)s - %(levelname)s:%(funcName)s: %(message)s"
LOG_FORMAT_DATE = "%H:%M:%S %m/%d"
logging.basicConfig(
    format=LOG_FORMAT, datefmt=LOG_FORMAT_DATE, level=LOG_LEVEL_DEFAULT
)

# Constants to aid in parsing of duckyscript
# Add repeat command
COMMANDS = ('REM', 'DEFAULT_DELAY', 'DELAY', 'STRING', 'REPEAT')
# Aliases for the above commands that will also be accepted
ALIAS = {
    'DEFAULTDELAY': 'DEFAULT_DELAY',
    'WINDOWS': 'GUI',
    'MENU': 'APP',
    'CONTROL': 'CTRL',
    'DOWNARROW': 'DOWN',
    'UPARROW': 'UP',
    'LEFTARROW': 'LEFT',
    'RIGHTARROW': 'RIGHT',
    'BREAK': 'PAUSE',
    'ESC': 'ESCAPE',
}
# Special conversions from duckyscript commands/keys to key names
# used by pyautogui. If a key is not listed below, then it will be
# assumed that its pyautogui name is the same as its duckyscript
# name in all lowercase
TRANSLATE_KEYS = {
    'GUI': 'command' if sys.platform == 'darwin' else 'winleft',
    'APP': 'apps'
}


# Below functions are used in DuckyCommand


def _set_args(func, *args, **kwargs):
    """
    Decorator that returns a new function which will execute the
    given function with the given arguments. Allows for a function's
    arguments to be set ahead of time. The returned function will
    not take in any arguments and will have the following attributes:

        * args: arguments that were passed to the wrapped function
        * kwargs: kwargs that were passed to the wrapped function
        * __name__: Will be overwritten with the wrapped function's
            name.

    :param func: Function to set the arguments for.
    :param args: Arguments to pass to ``func``.
    :param kwargs: Keyword arguments to pass to ``func``.
    :return: Function that when executed, will call the given function
        with the given arguments.
    """

    def wrapped():
        return func(*args, **kwargs)

    wrapped.args = args
    wrapped.kwargs = kwargs
    wrapped.__name__ = func.__name__

    return wrapped


def _cmd_rem(comment):
    """
    Function that just takes in a comment and does nothing with it to
    simulate the ``REM`` command.

    :param str comment: Comment string passed to the REM command.
    :return: None
    """

    pass


def _cmd_delay(ms):
    """
    Simulates the ``DELAY`` command by sleeping for the given number of
    milliseconds.

    :param int ms: Number of milliseconds to sleep.
    :return: None
    """

    time.sleep(ms / 1000)


def _cmd_repeat(dcmd, num_times):
    """
    Simulates the ``REPEAT`` command by continually executing the given
    :py:class:`DuckyCommand` for ``num_times`` number of times.

    :param DuckyCommand dcmd: Command to repeat
    :param int num_times: Number of times to repeat
    :return: None
    """

    # tell command to not set default delay
    dcmd._skip_delay = True

    # execute
    for num in range(num_times):
        dcmd.execute()

    # reset delay
    dcmd._skip_delay = False


def is_valid_alias(dcmd):
    """
    Checks to see if the given ducky command is an alias (i.e. in the
    global variable ``ALIAS``), returning ``True`` if it is. If the
    given command is not an alias for another, then ``False`` is
    returned.

    .. note:: ``False`` will still be returned if a command is given
       that has an alias. For instance, ``is_alias('ESC')`` is
       ``True``, ``is_alias('ESCAPE')`` is ``False``.

    :param str dcmd: Duckyscript command to check (case sensitive).
    :rtype: bool
    """

    return str(dcmd) in ALIAS.keys()


def get_alias_target(dalias):
    """
    Returns the duckyscript command that the given duckyscript alias
    targets.

    :param str dalias: Duckyscript alias (case sensitive)
    :return: Duckyscript command the alias targets.
    :raises ValueError: If given duckyscript alias is not valid
        (this includes if the given duckyscript command is not an
        alias).
    """

    if not is_valid_alias(dalias):
        raise ValueError(
            "Given alias '{}' is not a valid alias.".format(dalias)
        )

    # None should never be returned, as we guaranteed dalias is a key
    # in ALIAS through the is_valid_alias function
    return ALIAS.get(dalias, None)


def get_alias(dcmd):
    """
    Returns the known alias for the given ducky command. If the
    given command does not have an alias, then ``None`` is returned.

    :param str dcmd: Duckyscript command to get the known alias of
        (case sensitive).
    :return: Command's alias if it exists, or ``None``.
    :raises ValueError: if given ducky command is invalid.
    :raises TypeError: if the given ducky command is already an alias.
    """

    # check if command is valid
    if not is_valid_cmd(dcmd):
        raise ValueError(
            "Given command '{}' is not quackable/valid.".format(dcmd)
        )
    # we can't get the command's alias if its already an alias
    elif is_valid_alias(dcmd):
        raise TypeError(
            "Given command '{}' is already an alias.".format(dcmd)
        )

    for alias, cmd in ALIAS.items():
        if dcmd == cmd:
            return alias
    return None


def translate_key(dkey):
    """
    Translates the given duckyscript key into a ``pyautogui`` key
    name. A three step process is used to to this:

        1. Check if the key is an alias, and if it is, get its target.
        2. Translate the key using either ``TRANSLATE_KEYS`` if the key
           has a special translation or by setting the key to all
           lowercase. If a key such as ``CTRL-ALT`` is given (two key
           modifier) then each key in the macro will be translated
           individually.
        3. Check if the key is found in ``pyautogui.KEYBOARD_KEYS``,
           returning ``None`` if it isn't found.

    A tuple of the translated key is returned, so that it may be
    passed right into ``pyautogui`` commands even if more than one
    key is translated in the case a modifier was given.

    :param str dkey: Duckyscript key to translate.
    :rtype: tuple
    :return: ``pyautogui`` name of the given key inside a tuple if it
        could be translated, otherwise ``(None, )``. If a given key
        name translates to more than one key, then a tuple of each key
        is returned (i.e. ``CTRL-ALT`` -> ``('ctrl', 'alt')``)
    """

    # check if a two key modifier was given
    if '-' in dkey:
        return tuple(translate_key(key)[0] for key in dkey.split('-'))

    # Keys can also be used as commands, so get alias target if necessary
    if is_valid_alias(dkey):
        dkey = get_alias_target(dkey)

    # Use the TRANSLATE_KEYS dictionary if the key has a special conversion,
    # otherwise just set its keys to all lowercase
    pykey = TRANSLATE_KEYS.get(dkey, dkey).lower()

    # Check the key is found in pyautogui.KEYBOARD_KEYS
    if pykey not in pyautogui.KEYBOARD_KEYS:
        return (None, )  # rtype needs to be tuple

    return (pykey, )  # rtype needs to be tuple


def is_valid_cmd(dcmd):
    """
    Checks to see if the given ducky command is valid. Note that if
    a command is not valid in the eyes of this function, then the
    interpreter will not be able to executed it.

    :param str dcmd: Duckyscript command to check the validity of
        (case sensitive). Aliases and keys can also be given.
    :rtype: bool
    :return: ``True`` if valid, ``False`` otherwise
    """

    # try translating it as a key
    if None in translate_key(dcmd):
        # not a key, so return whether or not it is a recognized command
        return dcmd in COMMANDS
    else:
        return True


class DuckyCommand(object):
    """
    Execute a line of duckyscript in Python. Will log to the logger
    entitled **duckpy**.

    :param str dline: Raw duckyscript line to execute/model.
    :param int lineno: Line number of the given duckyscript line if
        it is a part of a script (defaults to ``-1``, which indicates
        the line is not in a script).
    :param int default_delay: Default delay to use while executing.
        Essentially determines how long to wait before executing a
        command (except in the case of ``REM``, where this delay is
        skipped).
    :param dict script: Dictionary of :py:class:`DuckyScript` methods
        used for setting default delays and repeating commands. Used
        internally by the :py:class:`DuckyScript` class (see
        :py:meth:`DuckyScript.load`).
    :raises ValueError: If ``scripts`` kwarg does not contain all
        necessary keys for execution.
    """

    def __init__(self, dline, lineno=-1, default_delay=0, script=None):
        """
        Construct the command.
        """

        # Logger
        self.logger = logging.getLogger('duckpy')

        # Whether or not to skip delay before executing command, in the
        # case of a comment
        self._skip_delay = False
        # default delay to use
        self._default_delay = default_delay
        # script object to use, check to make sure all keys present
        if script:
            for key in ('get_default_delay', 'set_default_delay', 'commands'):
                if script.get(key, None) is None:
                    raise ValueError(
                        "Expected key '{}' in 'script' argument not "
                        "found".format(key)
                    )
        self._script = script

        # Line number of this command in the script
        self.lineno = lineno

        # Raw duckyscript line to execute
        self.raw_line = dline
        # Python function that models the duckyscript
        self.python_func = self._to_python(dline)

    def __repr__(self):
        return "DCMD:'{}'".format(self.raw_line)

    @property
    def default_delay(self):
        """
        default_delay property. Value of this property will be
        determined by whether or not this command is a part of a
        script. If it is, then the script's default delay value will
        be used, otherwise this instance's value will be used.

        :rtype: int
        :return: default delay being used by the command
        :raise KeyError: If get_default_delay method of script cannot
            be found in :py:attr:`_script`.
        """

        if self._script:
            # shouldn't raise an error, but going to check anyways
            try:
                return self._script['get_default_delay']()
            except KeyError as e:
                # change the error message and re-raise
                e.args = (
                    "Unable to get default delay for script (missing "
                    "`get_default_delay` function)",
                )
                raise
        else:
            return self._default_delay

    @default_delay.setter
    def default_delay(self, new_delay):
        """
        Create the setter for the default_delay property. Setting the
        default delay depends on whether or not this command is a part
        of a script. If so, then the command will set the default delay
        for the script, otherwise this instance's value will be used.

        :raise KeyError: If set_default_delay method of script cannot
            be found in ``self._script``
        """

        if self._script:
            try:
                self._script['set_default_delay']()
            except KeyError as e:
                # change error message and re-raise
                e.args = (
                    "Unable to set default delay for script (missing "
                    "`set_default_delay` function)",
                )
                raise
        else:
            self._default_delay = new_delay

    def _to_python(self, dline):
        """
        Parses the given duckyscript line into a Python function. The
        command in the line (i.e. the substring that lies before the
        first space) will be parsed and then matched against known
        commands. If a match is found, the appropriate Python function
        is constructed and returned. If a match is not found, a
        function will still be constructed and returned, however the
        line will be interpreted as a series of keys to press instead
        of a command (for instance if ``GUI r`` was given, ``GUI`` will
        be seen as a key and not a command). A pre-check is done prior
        to the matching process, to ensure that the given command/key
        combo is valid.

        Here's a list of translations for commands and their Python
        functions:

        * REM: :py:func:`duckpy.duck._cmd_rem`
        * DELAY: :py:func:`duckpy.duck._cmd_delay`
        * DEFAULT_DELAY: This is done internally, see the default_delay
          parameter in the source code for details.
        * STRING: :py:func:`pyautogui.typewrite`
        * REPEAT: This is again done internally, see source code for more
          details.
        * (Other): :py:func:`pyautogui.hotkey`.

        :param str dline: Duckyscript line to translate.
        :return: Python function that when executed, will simulate the
            given duckyscript line.
        :raises ValueError: If an invalid command is given.
        """

        # we just want ['COMMAND', 'ARG']
        self.logger.debug("Parsing to quackable python: '{}'".format(dline))
        dline = dline.strip().split(' ', maxsplit=1)
        if not is_valid_cmd(dline[0]):
            msg = "Given command '{}' is not quackable.".format(dline[0])
            self.logger.error(msg)
            raise ValueError(msg)
        else:
            # Translate the command if it is an alias
            if is_valid_alias(dline[0]):
                dline[0] = get_alias_target(dline[0])
                self.logger.debug(
                    "Given command is an alias for '{}'".format(dline)
                )

            # Go through possible commands, using python equivalents
            if dline[0] == 'REM':
                self.logger.debug(
                    "Got command REM with comment: {!r}".format(dline[1])
                )
                # REM commands aren't delayed with the default delay
                self._skip_delay = True
                # emulate using _cmd_rem
                return _set_args(_cmd_rem, dline[1])

            elif dline[0] == 'DELAY':
                self.logger.debug(
                    "Got command DELAY with sleep param: {}".format(dline[1])
                )
                # emulate using _cmd_delay
                return _set_args(_cmd_delay, int(dline[1]))

            elif dline[0] == 'DEFAULT_DELAY':
                self.logger.debug(
                    "Got command DEFAULT_DELAY with sleep param: {}".format(
                        dline[1]
                    )
                )
                # emulate with instance method
                return _set_args(
                    self._script['set_default_delay'], int(dline[1])
                )

            elif dline[0] == 'STRING':
                self.logger.debug(
                    "Got command STRING with text: {!r}".format(
                        dline[1]
                    )
                )
                # use pyautogui.typewrite to write out the given string
                return _set_args(pyautogui.typewrite, str(dline[1]))

            elif dline[0] == 'REPEAT':
                self.logger.debug(
                    "Got command REPEAT with num: {}".format(dline[1])
                )

                try:
                    to_repeat = self._script['commands'][self.lineno - 1]
                # 'commands' not found
                except KeyError as e:  # 'commands' not found
                    msg = "Unable to parse REPEAT command, as access to " \
                          "list of commands in script was not given " \
                          "(missing `commands` in `_script`."
                    self.logger.error(msg, exc_info=True)
                    e.args = (msg, )
                    raise
                # first command in script, so just do nothing
                except IndexError:
                    to_repeat = _cmd_rem

                # use repeat command
                return _set_args(_cmd_repeat, to_repeat, int(dline[1]))

            else:  # given a key to press
                # translate_key return data will be a tuple of tuples, so
                # use sum to 'add' the tuples together into one tuple (unpack)
                keys = sum(tuple(translate_key(key) for key in dline), ())
                self.logger.debug(
                    "Was given following keys to press: '{}'".format(
                        ','.join(keys)
                    )
                )

                # these keys should not be None, as is_valid_cmd verifies
                # they are valid
                # pyautogui.hotkey will also press single keys
                return _set_args(pyautogui.hotkey, *keys)

    def execute(self):
        """
        Execute the line of duckyscript that was given during class
        construction. This will block until finished.

        :return: None
        """

        self.logger.debug(
            "Executing line {}: '{}'".format(self.lineno, self.raw_line)
        )

        # Sleep default delay if necessary
        if not self._skip_delay:
            self.logger.debug(
                "Sleeping for {} milliseconds (default delay)".format(
                    self.default_delay
                )
            )
            _cmd_delay(self.default_delay)

        # call function
        self.logger.debug("Calling python function")
        self.python_func()
        self.logger.debug("Finished")


class DuckyScript(object):
    """
    Representation of a duckyscript file. Allows for reading, parsing
    and execution. The given Duckyscript file to represent will be
    parsed and loaded on creation.

    :param str dpath: Path to duckyscript (text) file
    :raises OSError: If given path to a duckyscript file either
        does not exist or cannot be read.
    """

    def __init__(self, dpath):
        """
        Construct the script.
        """

        # create a logger
        self.logger = logging.getLogger('duckpy')
        # where commands will be stored
        self.commands = []
        # set default delay
        self._default_delay = 0

        # create a script 'interface' that commands will use for
        # default delay and repeats
        self._script = {
            'set_default_delay': self._set_default_delay,
            'get_default_delay': self._get_default_delay,
            'commands':  self.commands
        }

        # check if the file exists and is not a directory
        if not os.path.exists(dpath):
            raise OSError(
                "Given script to load at does not exist: {}".format(dpath)
            )
        elif os.path.isdir(dpath):
            raise OSError(
                "Given path to load as a script is a directory, not a "
                "file: {}".format(dpath)
            )
        else:
            # save script location
            self.script_path = dpath

    def _set_default_delay(self, new_delay):
        """
        Method for setting the `default_delay` attribute. This is
        given to `DuckyCommand` instances so that they may set the
        default delay for the script.

        :param int new_delay: New default delay to set.
        """

        self._default_delay = new_delay

    def _get_default_delay(self):
        """
        Method for retreiving the `default_delay` attribute. This is
        given to `DuckyCommand` instances so that they may get the
        default delay for the script.

        :return: `_default_delay`
        """

        return self._default_delay

    @property
    def default_delay(self):
        """
        default_delay property, using `_get_default_delay` as the
        getter method. default_delay is made into a property so the
        getter and setter methods can be passed onto children
        :py:class:`DuckyCommand` instances.
        """

        return self._get_default_delay()

    @default_delay.setter
    def default_delay(self, new_delay):
        """
        Create the setter method for the default delay property, using
        `_set_default_delay`.

        :param int new_delay: New delay to set.
        """

        self._set_default_delay(new_delay)

    def load(self):
        """
        Loads the duckyscript and parses it into python functions for
        execution. Note that every time this method is called the
        duckyscript will be read and parsed (i.e. this method supports
        reloading of scripts).

        :raises ValueError: If line in duckyscript file cannot be
            parsed.
        :return: None
        """

        # check if the script has already been loaded
        if type(self.commands) == tuple:
            self.logger.warning(
                "Script at '{}' has already been loaded. "
                "Reloading".format(self.script_path)
            )
            self.commands = []

        self.logger.info("Loading script at '{}'".format(self.script_path))

        # open and read file
        self.logger.debug("Opening file")
        with open(self.script_path, 'r') as dfile:
            for lineno, line in enumerate(dfile):

                # log the line
                self.logger.info(
                    "Got line (lineno: {}): {!r}".format(lineno, line)
                )

                # strip line of any whitespace (including newlines)
                line = line.strip()
                # check that the line isn't just an empty newline
                if len(line) > 0:
                    self.logger.debug("Parsing into ducky command")
                    try:
                        # create object
                        dcmd = DuckyCommand(
                            line, lineno=lineno, script=self._script
                        )

                        # append to command list
                        self.commands.append(dcmd)
                    except Exception as e:
                        # log the error and raise again
                        msg = "Unable to parse line at {}: {!r}".format(
                            lineno, line
                        )
                        self.logger.error(msg, exc_info=True)
                        # reraise the error
                        raise

        # cast self.commands to tuple so we know if its already been
        # loaded
        self.commands = tuple(self.commands)

        self.logger.info("Finished loading")

    def run(self):
        """
        Runs the duckyscript file (loading it if necessary) by
        executing all of the parsed commands sequentially. Will 'pass
        through' any errors that may possibly occur during execution.

        :return: None
        """

        if type(self.commands) != tuple:
            self.logger.debug("Loading script")
            self.load()

        self.logger.info("Executing script at: '{}'".format(self.script_path))

        for cmd in self.commands:
            try:
                self.logger.info(
                    "Running line {}: {!r}".format(cmd.lineno, cmd.raw_line)
                )
                cmd.execute()
            except Exception as e:
                msg = "An exception occurred while executing " \
                      "line {}: {}".format(cmd.lineno, e)
                self.logger.error(msg, exc_info=True)

                # raise the exception, as can't go on if an error occurred
                raise

        self.logger.info("Finished execution")


def main(cli_args=None):
    """
    Takes in a duckyscript file, parses it and executes it. This
    function can be called by executing `python -m duckpy` however it
    can also be called manually by passing command line arguments
    through ``args``)

    :param str cli_args: Pass command line arguments directly.
        Example: ``"my_payload.txt -v"``
    :return: None
    """

    # create an argument parser
    parser = argparse.ArgumentParser(
        description="duckpy: Duckyscript interpreter written in Python",
        prog="duckpy"
    )

    # add arguments
    parser.add_argument(
        "dscript", help="duckyscript file to execute (should be plaintext)"
    )
    parser.add_argument(
        "-v", "--verbose", help="Print log messages to screen (level INFO)",
        action='store_true', default=False
    )
    parser.add_argument(
        "-vv", "--vverbose", help="Print log messages to screen (level "
                                  "DEBUG). Note that this will print a "
                                  "lot of output.",
        action='store_true', default=False
    )

    # parse
    if cli_args:
        # pass in given cli arguments string
        args = parser.parse_args(cli_args.split(' '))
    else:
        # otherwise get arguments from call
        args = parser.parse_args()

    # setup logging levels
    log_level = LOG_LEVEL_DEFAULT  # should be set to warning
    if args.vverbose:
        log_level = logging.DEBUG
    elif args.verbose:
        log_level = logging.INFO
    logging.getLogger('duckpy').setLevel(log_level)

    # execute script and exit
    script = DuckyScript(args.dscript)
    script.run()


if __name__ == '__main__':
    main()
