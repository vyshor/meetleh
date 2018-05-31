import telepot
from telepot.loop import MessageLoop
from copy import deepcopy
import pickle
import time
import datetime
import pywapi
from telepot.namedtuple import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, \
    InlineKeyboardButton


# And in the event if you want to run the bot, remember to change the TOKEN,
# and ctrl+F search for "meetlehbot" and replace the necessary places with your botname
# This is to allow deeplinking to work
# And also remember to disable the code below where library pickles is used to open a previous
# saved file to save the data structure somewhere
# And also remember install telepot and pywapi beforehand
# Credits to telepot and pywapi for their library
# (This whole script is built and ran on Pycharm, so if there is any possible chance of incompatability,
# please use pyCharm then and the script contains some special characters for use of emojis)

PRE_EVENT = {}
EVENT = {}
DATABASE = {}
DEEP_LINK = {}
USEREVENTS = {}
NAMES = {}
CHATCOUNT = {}
WEATHER = {}

# Brief idea of how the whole data structure works
# PRE_EVENT is main data structure that keeps all the info when user making the event
# from the start of /createevent in private chat to confirm event button
#
# From there, the event_id, qns and ans are moved into DATABASE
#
# Then as user share their poll into a group, they bring create a new eventid
# the new eventid consist of the previous event_id (which is used to keep tracked of original
# qns and ans) and the group_id he shared it to
# this allows every NEW event_id be unique, such that the same event can be shared into different groups
# However, if they wish to share into same group, it would be detected and only refreshes the chat (refresh means bring
# the chat down for everyone to see) (kind of like reminding everyone at same time) this is to prevent people in the
# same group joining multiple of same events in the group itself, making it confusing
#
# Then once, it is shared in the group, the qns and ans are extracted from DATABASE
# and saved into some parts of EVENT
# EVENT contains a data structure, holding all the user_id, the id of the msg bot send to them (a.k.a update.id),
# and their choices (whether they picked the ans as their options or not)
# At the same time, there is a "default" user in EVENT to keep a backup copy of the qns
#
# Yet, the "default" user also act as a portable indicator if the admin have decided to finish collating
# everyones' vote and decided to move on in creating the event
# parts of the "default" are then reused  to store the list of users who agreed on selected choice, and the names of them
#
# Then the next part is when the admin is filling up the details of the event to be confirmed
# Because it is difficult to differentiate which user wants to key in, I often use PRE_EVENT[chat_id][1] (which
# is supposed to be used to store the qns of the PRE_EVENT part) by changing them into negative values to indicate
# the next user input is what he supposed to input in. This is to prevent user abuses, when he decided to
# press other buttons when he are supposed to key in some values, which can cause alot problems, especially when trying
# to make everything standalone and independent from each other.
#
# Having such a complicated data structure is to ease searching and increase loading time, considering telegram is always slow
# Below is the brief data structure that is used as a guide (P.S. it can be confusing until you learn
# about whole data structure)
#
# PRE_EVENT[admin.id] = [event_chatid,qns,ans,articles]     #Funfact: articles was supposed to be used together with on_inline_query,
# EVENT[grp.id][event.id] =                                  #         but was scrapped because  we found a better way, using DEEPLINKING
# [details, choices =[chat.id: update.id ,c1, c2], admin.id, Univupdate.id]
# DATABASE[event.id] = [qns, ans]
# USEREVENTS[chat.id] = [grpchat1.id, grpchat2.id]
# NAMES[chat.id] = name
# DEEP_LINK[event.id] = [admin.id, grp.id]
# CHATCOUNT[chat.id] = count
# WEATHER[event.id] = [datetime, datetext, locationkey, weathertext, locationtext]
#
# Lastly, credits to telepot to allow working around telegram bots on python
# and pywapi for weather forecast scrapping and data

# used pickles to save the data structure and keep as backup and keep it running
# f = open('store.p', 'rb')
# PRE_EVENT, EVENT, DATABASE, DEEP_LINK, USEREVENTS, NAMES, CHATCOUNT, WEATHER = pickle.load(f)
# f.close()

names = ["Change Qns", "Remove Last Option"]
namefunc = ["change", "remove"]
keypad = InlineKeyboardMarkup(
    inline_keyboard=[
        list(map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d)), names, namefunc)),
        [InlineKeyboardButton(text="Confirm", callback_data='confirm')]])


def on_chat_message(msg):
    content_type, chat_type, chat_id = telepot.glance(msg)  # private chat
    message = msg['text'].split()
    command = message[0]
    global PRE_EVENT
    global EVENT
    global DEEP_LINK
    global USEREVENTS
    global NAMES
    global CHATCOUNT
    global keypad
    global WEATHER

    print(msg['from']['first_name'] + "(" + str(chat_id) + ") : " + msg['text'] + " ")
    NAMES[chat_id] = msg['from']['first_name']  # store everyone names

    if chat_id in PRE_EVENT.keys() and type(PRE_EVENT[chat_id][1]) == int and PRE_EVENT[chat_id][1] <= -1 and command != '/createevent' and command != '/start':
        # must be first, cus he setting details for event and nothing else

        warning = ""
        event_id = PRE_EVENT[chat_id][2][-1]  # get last element
        foundevent = eventfinder(event_id)

        if any(c in msg['text'] for c in '<>/&`_'):
            warning = "\n<b>Special characters are not allowed.</b>"
        else:
            eventdetails = PRE_EVENT[chat_id][2][-2]
            if PRE_EVENT[chat_id][1] == -1:  # means he setting details for event
                PRE_EVENT[chat_id][2].pop()
                foundevent[0] = msg['text']
            else:
                foundevent[0] = eventdetails
                if PRE_EVENT[chat_id][1] == -2:
                    date = msg['text'].split('-')
                    try:  # if got it cannot even convert to integer
                        if len(date) == 3 and 0 < int(date[0]) <= 9999 and 0 < int(date[1]) <= 12 and 0 < int(date[1]) <= 31:
                            WEATHER[event_id][0] = datetime.datetime(int(date[0]), int(date[1]), int(date[2]), 0, 0, 0)
                            WEATHER[event_id][1] = date[2] + "/" + date[1] + "/" + date[0]
                    except:
                        warning = "\n<b>Invalid format for date</b>"
                    today = datetime.datetime.now()
                    chance = ""
                    if WEATHER[event_id][2]:  # not an empty list
                        if (WEATHER[event_id][0] - today).days >= 6:
                            bot.sendMessage(chat_id, "Too far away to get weather forecast")
                            return
                        else:
                            chance = int(pywapi.get_weather_from_weather_com(WEATHER[event_id][2])['forecasts'][
                                (WEATHER[event_id][0] - today).days - 1]['day']['chance_precip'])
                    else:
                        bot.sendMessage(chat_id, "Set the place too to get weather forecast")
                    if type(chance) == int:
                        WEATHER[event_id][3] = "☀ Sunny ☀"
                        if chance >= 30:
                            WEATHER[event_id][3] = "⛅ Cloudy ⛅"
                        if chance >= 50:
                            WEATHER[event_id][3] = "🌧 Rain 🌧"
                        if chance >= 70:
                            WEATHER[event_id][3] = "🌩 Thunderstorm 🌩"

                elif PRE_EVENT[chat_id][1] == -3:
                    location = msg['text']
                    WEATHER[event_id][4] = location
                    temp_dict = pywapi.get_location_ids(location)
                    WEATHER[event_id][2] = [k for k in temp_dict]
                    if WEATHER[event_id][2]:  # means not empty
                        temp_msg2 = ""
                        n = 1
                        for v in temp_dict.values():
                            temp_msg2 += "%i. %s \n" % (n, v)
                            n += 1
                        temp_msg2 += "<b>Please type in the number of choice</b>"

                        PRE_EVENT[chat_id][1] = -4
                        CHATCOUNT[chat_id] = 3  # instantly refreshes and brings to bottom again
                        textrefresh(temp_msg2, foundevent[1][chat_id], foundevent[1][chat_id][0], chat_id, None, 'HTML')
                        return  # terminate
                    else:
                        warning = "\n<b>No search results of the place.</b>"
                elif PRE_EVENT[chat_id][1] == -4:
                    try:
                        chance = ""
                        temp_msg2 = WEATHER[event_id][2][int(msg['text']) - 1]
                        WEATHER[event_id][2] = temp_msg2
                        today = datetime.datetime.now()
                        if WEATHER[event_id][0] != 0:  # set date first alr
                            if (WEATHER[event_id][0] - today).days >= 6:
                                bot.sendMessage(chat_id, "Too far away to get weather forecast")
                                return
                            else:
                                chance = int(pywapi.get_weather_from_weather_com(temp_msg2)['forecasts'][(WEATHER[event_id][0] - today).days - 1]['day']['chance_precip'])
                        else:
                            bot.sendMessage(chat_id, "Set the date too to get weather forecast")
                        if type(chance) == int:
                            WEATHER[event_id][3] = "☀ Sunny ☀"
                            if chance >= 30:
                                WEATHER[event_id][3] = "⛅ Cloudy ⛅"
                            if chance >= 50:
                                WEATHER[event_id][3] = "🌧 Rain 🌧"
                            if chance >= 70:
                                WEATHER[event_id][3] = "🌩 Thunderstorm 🌩"
                        PRE_EVENT[chat_id][1] = eventdetails
                    except:  # in case type in is not integer or not within the choices
                        bot.sendMessage(chat_id, "Invalid input, Please key in another choice")
                        return  # so it will ask for another choice again
                PRE_EVENT[chat_id][2].pop()  # remove event_id
            PRE_EVENT[chat_id][2].pop()  # remove event details from temp storage
            PRE_EVENT[chat_id][1] = PRE_EVENT[chat_id][2].pop()  # done borrowing some space, set it back to original
        options2 = ["Erase", "Back"]
        optionsent2 = ["erase", "initiate"]
        options4 = ["Set Date", "Set Place"]
        optionsent4 = ["date", "place"]
        options3 = ["Attendance", "Cancel"]
        optionsent3 = ["attend", "cancel"]
        vote = InlineKeyboardMarkup(inline_keyboard=[list(
            map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options2,
                optionsent2)),
            list(
                map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options4,
                    optionsent4)),
            list(
                map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options3,
                    optionsent3)),
            [InlineKeyboardButton(text="Confirm", callback_data=str("confirmpluschop" + '`' + event_id))]])
        locationtext = ""
        if type(WEATHER[event_id][4]) == str:
            locationtext = "\nLocation: " + WEATHER[event_id][4] + "\n"
        CHATCOUNT[chat_id] = 3  # instantly refreshes and brings to bottom again
        textrefresh("<b>" + foundevent[0] + "\nDate: " + WEATHER[event_id][1] + "\n" + locationtext + WEATHER[event_id][3] + "</b>\n" + foundevent[1]["default"][0] + warning,
                    foundevent[1][chat_id], foundevent[1][chat_id][0], chat_id, vote, 'HTML')

        return  # must terminate

    if command == '/createevent' and msg['chat']['type'] == 'private':  # check if its private chat
        try:
            antieventdetails(chat_id)
            if type(PRE_EVENT[chat_id][1]) != str and not PRE_EVENT[chat_id][2]:  # means no qns n empty ans
                event_chatid = telepot.message_identifier(bot.sendMessage(chat_id, "Hello"))
                PRE_EVENT[chat_id] = [event_chatid, 1, [], []]
                PRE_EVENT[chat_id][
                    1] = "Meet up next week? Put days free for next week"  # set 1 to check nxt msg for the qns or not
                PRE_EVENT[chat_id][2] = ["Mon", "Tue", "Wed", "Thurs", "Fri", "Sat", "Sun"]

                temp_msg = ""
                for x in range(0, len(PRE_EVENT[chat_id][2])):
                    temp_msg += "\n" + str(x + 1) + ". " + PRE_EVENT[chat_id][2][x]

                options = ["Use default", "Edit"]
                optionsent = ["confirm", "edit"]

                vote = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d)), options, optionsent)),
                    [InlineKeyboardButton(text="New", callback_data="new")]])
                bot.editMessageText(event_chatid, "<b>Default Settings:</b>\n" + PRE_EVENT[chat_id][1] + temp_msg,
                                    reply_markup=vote, parse_mode='HTML')

            else:  # otherwise it means there is a current create event going through
                options = ["Continue", "New Event"]
                optionsent = ["cont", "abandon"]

                vote = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d)), options, optionsent))])

                qns = "(No question provided)"
                if type(PRE_EVENT[chat_id][1]) == str:  # if qns is provided
                    qns = PRE_EVENT[chat_id][1]

                temp_msg = ""
                if PRE_EVENT[chat_id][2]:  # to check if list is not empty
                    temp_msg = ""
                    for x in range(0, len(PRE_EVENT[chat_id][2])):
                        temp_msg += "\n" + str(x + 1) + ". " + PRE_EVENT[chat_id][2][x]

                CHATCOUNT[chat_id] = 3  # move the chat up
                textrefresh('<b>' + qns + "</b>" + temp_msg + "\n\n<b>Continue your previous event?</b>",
                            PRE_EVENT[chat_id], PRE_EVENT[chat_id][0], chat_id, vote, "HTML")

        except KeyError:  # means first time create event or he ended previous event
            event_chatid = telepot.message_identifier(bot.sendMessage(chat_id, "Hello"))
            PRE_EVENT[chat_id] = [event_chatid, 1, [], []]
            PRE_EVENT[chat_id][1] = "Meet up next week? Put days free for next week"  # set 1 to check nxt msg for the qns or not
            PRE_EVENT[chat_id][2] = ["Mon", "Tue", "Wed", "Thurs", "Fri", "Sat", "Sun"]

            temp_msg = ""
            for x in range(0, len(PRE_EVENT[chat_id][2])):
                temp_msg += "\n" + str(x + 1) + ". " + PRE_EVENT[chat_id][2][x]

            options = ["Use default", "Edit"]
            optionsent = ["confirm", "edit"]

            vote = InlineKeyboardMarkup(inline_keyboard=[list(
                map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d)), options, optionsent)),
                [InlineKeyboardButton(text="New", callback_data="new")]])
            bot.editMessageText(event_chatid, "<b>Default Settings:</b>\n" + PRE_EVENT[chat_id][1] + temp_msg, reply_markup=vote, parse_mode='HTML')

            # if not created yet
        return  # terminate to reduce running load

    if command == '/start@meetlehbot':  # needs to be changed corresponding to botname
        try:
            command, payload = message
            print(msg['from']['first_name'] + "(" + str(chat_id) + ") payload: " + payload + " ")
            linking(msg, payload)
        except ValueError:
            print(msg['from']['first_name'] + "(" + str(chat_id) + ") payload: NO PAYLOAD ")
            return  # terminate

        event_id = payload + '_' + str(chat_id)  # new event id that includes grpid

        if EVENT and chat_id in EVENT.keys() and event_id in EVENT[chat_id].keys():  # means they send to this grp before alr
            # then pop out the old poll or alr created event
            # so need to check if its old poll with join button only or the alr created event
            # only way to check is to see the "default"[1] is list -> list of ppl alr in created event
            # or str, cus it is one of the options, means old poll

            # another case i miss out is what happens if voting ended, then admin can see how
            # much of each vote, then the admin decides share again, which screw things up
            # then from here, i guess we check if the universalchatidforgrp still exist or not
            foundevent = eventfinder(event_id)
            if foundevent[3] == -1:  # indication of after voting and pre-alr created event
                # i guess we just quote and forward the message, so user can click and scroll up to it
                admin_id = DEEP_LINK[event_id][0]
                bot.sendMessage(admin_id, "<b>You have already collated the results</b>",
                                reply_to_message_id=foundevent[1][admin_id][0][1], parse_mode='HTML')
                return  # must terminate

            elif type(foundevent[1]["default"][1]) == str:
                CHATCOUNT[chat_id] = 3  # allow text message to refresh/bring to bottom for grp chat
                joinpad = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='Join', url='https://telegram.me/meetlehbot?start=%s' % event_id)]])
                textrefresh(DATABASE[removegrpid(event_id)][0], foundevent, foundevent[3], chat_id, joinpad, 'HTML')

                # then u want refresh admin chat also
                # and it can only happen at the voting stage
                # then just need

                admin_id = DEEP_LINK[event_id][0]

                options = DATABASE[removegrpid(event_id)][1]
                optionsent = []
                for element in options:
                    optionsent.append(element + str(options.index(element)))

                vote = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c),
                                                          callback_data=str("choice" + '`' + event_id + '`' + d)),
                        options, optionsent)),
                    [InlineKeyboardButton(text="Confirm Event", callback_data=str("confirmevent" + '`' + event_id))]])
                if admin_id in foundevent[1].keys():  # check admin join yet or not
                    CHATCOUNT[admin_id] = 3
                    textrefresh(adminchat(event_id), foundevent[1][admin_id], foundevent[1][admin_id][0], admin_id, vote, 'HTML')
                return  # must terminate if not overprint msgs

            elif type(foundevent[1]["default"][1]) == list:
                # this is when people already choosing between to join/confirm/leave
                # so u refresh the join/confirm/leave in group and admin chat
                CHATCOUNT[chat_id] = 3
                locationtext = ""
                if type(WEATHER[event_id][4]) == str:
                    locationtext = "\nLocation: " + WEATHER[event_id][4] + "\n"
                temp_msg = "<b>" + foundevent[0] + "\nDate: " + WEATHER[event_id][1] + "\n" + locationtext + \
                           WEATHER[event_id][3] + "</b>\n" + foundevent[1]["default"][0]

                options = ["Join", "Confirm", "Leave"]
                optionsent = ["join", "assure", "leave"]
                vote = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)),
                        options,
                        optionsent))])
                textrefresh(temp_msg, foundevent, foundevent[3], chat_id, vote, 'HTML')
                # above is for grp chat
                # below is for admin chat
                # first need check if admin is in the grp that r going or not
                admin_id = DEEP_LINK[event_id][0]
                options2 = ["Join"]
                optionsent2 = ["join"]
                temp_msg = foundevent[1]["default"][0]
                if admin_id in foundevent[1]["default"][1]:  # means going ah
                    options2 = ["Confirm", "Leave"]
                    optionsent2 = ["assure", "leave"]
                vote2 = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)),
                        options2,
                        optionsent2))])
                # refresh text for admin chat also
                CHATCOUNT[admin_id] = 3
                textrefresh(temp_msg, foundevent[1][admin_id], foundevent[1][admin_id][0], admin_id, vote2,
                            'HTML')
                return  # must terminate if not over print messages

        grp_id = DEEP_LINK[event_id][1]
        try:
            EVENT[grp_id][event_id] = [0] * 4
        except KeyError:
            EVENT[grp_id] = {}
            EVENT[grp_id][event_id] = [0] * 4

        foundevent = eventfinder(event_id)
        foundevent[0] = DATABASE[removegrpid(event_id)][0]
        foundevent[2] = DEEP_LINK[event_id][0]  # admin_id
        foundevent[1] = {}
        foundevent[1]["default"] = DATABASE[removegrpid(event_id)][1].copy()  # set a default to easily reference
        # copy so that it does not point to same variable/ creating a diff set of copy

        if event_id not in WEATHER.keys():  # first timer
            WEATHER[event_id] = [0] * 5
            WEATHER[event_id][1] = ""
            WEATHER[event_id][2] = []
            WEATHER[event_id][3] = ""

        # provide deeplink for users to talk to bot
        joinpad = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Join', url='https://telegram.me/meetlehbot?start=%s' % event_id)]])  # needs to change to according to bot name
        foundevent[3] = telepot.message_identifier(bot.sendMessage(chat_id, DATABASE[removegrpid(event_id)][0],
                                                                   reply_markup=joinpad))
        return  # terminate to reduce running load

    if (command == '/start' or command == '/help') and msg['chat']['type'] == 'private':  # make sure private chat
        antieventdetails(chat_id)
        try:
            command, payload = message
            print(msg['from']['first_name'] + "(" + str(chat_id) + ") payload: " + payload + " ")
            linking(msg, payload)
        except ValueError:
            print(msg['from']['first_name'] + "(" + str(chat_id) + ") payload: NO PAYLOAD ")
            # show welcome messages
            temp_msg = "🤜🤛MeetLeh Bot🤜🤛\n\n/help - To see the commands\n/createevent -  To ask a broad qns and provide different options\n✍\"Shall we meet up nxt week?\"\nOptions: Mon/Tues/Wed/Thurs/Fri/Sat/Sun\nOR. Click on 'NEW' to design your own event and options\n👉Post on the group\n👉Wait for your groupmates to vote\n👉See the results\n👉Finalise on an exact date\n👉Update on group and people confirm their attendance"
            bot.sendMessage(chat_id, temp_msg, parse_mode='HTML')
            return  # terminate

        event_id = payload
        grp_id = DEEP_LINK[event_id][1]

        try:
            USEREVENTS[chat_id].append(grp_id)
        except KeyError:
            USEREVENTS[chat_id] = []
            USEREVENTS[chat_id].append(grp_id)

        foundevent = eventfinder(event_id)

        options = DATABASE[removegrpid(event_id)][1]
        optionsent = []
        for element in options:
            optionsent.append(element + str(options.index(element)))

        vote = InlineKeyboardMarkup(inline_keyboard=[list(
            map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str("choice" + '`' + event_id + '`' + d)),
                options, optionsent))])

        if chat_id in foundevent[1].keys():  # if user is /start before alr
            if chat_id == foundevent[2]:  # if user is admin

                vote = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c),
                                                          callback_data=str("choice" + '`' + event_id + '`' + d)),
                        options, optionsent)),
                    [InlineKeyboardButton(text="Confirm Event", callback_data=str("confirmevent" + '`' + event_id))]])
                temp_msg = adminchat(event_id)
            else:  # if user is not admin, only show his own choices only
                temp_msg = nonadminchat(event_id, chat_id)

            CHATCOUNT[chat_id] = 3
            textrefresh(temp_msg, foundevent[1][chat_id], foundevent[1][chat_id][0], chat_id, vote, 'HTML')
            # bring the chat back to below for him to see
        else:
            foundevent[1][chat_id] = [0] * (len(DATABASE[removegrpid(event_id)][1]) + 1)
            if chat_id == foundevent[2]:  # if user is admin

                vote = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c),
                                                          callback_data=str("choice" + '`' + event_id + '`' + d)),
                        options, optionsent)),
                    [InlineKeyboardButton(text="Confirm Event", callback_data=str("confirmevent" + '`' + event_id))]])
                temp_msg = adminchat(event_id)
            else:  # if user is not admin, only show his own choices only
                temp_msg = nonadminchat(event_id, chat_id)

            event_chatid = telepot.message_identifier(
                bot.sendMessage(chat_id, temp_msg, reply_markup=vote, parse_mode='HTML'))
            foundevent[1][chat_id][0] = event_chatid  # to change constantly

        return  # terminate to reduce running load

    if chat_id in PRE_EVENT:
        # must be placed at the end, cus it checks as long as chat_id in PRE_EVENT and terminates

        warning = ""  # warning text to tell him if he uses ` or same choice
        if PRE_EVENT[chat_id][1] == 1:
            if any(c in msg['text'] for c in '<>/&`_'):
                warning = "\n<b>Special characters are not allowed.</b>"
                textrefresh("Write the question for your event" + warning,
                            PRE_EVENT[chat_id], PRE_EVENT[chat_id][0], chat_id, None, "HTML")
                return  # must terminate if not it will overwrite
            else:
                PRE_EVENT[chat_id][1] = msg['text']
        elif type(PRE_EVENT[chat_id][1]) == str:
            if any(c in msg['text'] for c in '<>/&`_'):
                warning = "\n<b>Special characters are not allowed.</b>"  # prevent special chars
            elif msg['text'] in PRE_EVENT[chat_id][2]:
                warning = "\n<b>Please type a different option</b>"  # prevent repeats
            else:
                PRE_EVENT[chat_id][2].append(msg['text'])

        if PRE_EVENT[chat_id][1] != 0:  # check if setting of event ended or not
            qns = ""
            if type(PRE_EVENT[chat_id][1]) == str:
                qns = PRE_EVENT[chat_id][1]

            if PRE_EVENT[chat_id][2]:  # to check if list is empty or not
                temp_msg = ""
                for x in range(0, len(PRE_EVENT[chat_id][2])):
                    temp_msg += "\n" + str(x + 1) + ". " + PRE_EVENT[chat_id][2][x]
                textrefresh('<b>' + qns + "</b>\n\nWrite in the options you like to provide" + temp_msg + warning,
                            PRE_EVENT[chat_id], PRE_EVENT[chat_id][0], chat_id, keypad, "HTML")
            else:
                textrefresh('<b>' + qns + "</b>\n\nWrite in the options you like to provide" + warning,
                            PRE_EVENT[chat_id], PRE_EVENT[chat_id][0], chat_id, keypad, "HTML")
        return  # terminate to reduce running load

# This whole part below is scrapped and just left as comment as reference, on how we plan the structure from start
# def on_chosen_inline_result(msg):
#     global PRE_EVENT
#     global DATABASE
#
#     def createevent(msg):  # create event function
#         bot.sendMessage(from_id, "Yet to be done")  # save triggerer as admin
#         # linking(msg)  # function to link users to group (deeplinking) ---> trigger private vote
#
#     def checkevent(msg):  # check event function
#         bot.sendMessage(from_id, "To be added")
#
#     result_id, from_id, query_string = telepot.glance(msg, flavor='chosen_inline_result')
#     if result_id in DATABASE:  # create event trigger
#         createvent(msg)
#         return  # I need to get the group.id but idk how, i know how to use deep-linking, its either creating a button
#     # with a url link of https://telegram.me/<bot_username>?start=abcde or make use of
#
#     elif result_id == 'Check Event':  # check on events
#         checkevent(msg)


def on_callback_query(msg):
    query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
    global keypad
    global DATABASE
    global DEEP_LINK
    querylist = query_data.split('`')
    event_id = 0  # initialised
    querycommand = querylist[0]

    NAMES[from_id] = msg['from']['first_name']

    try:
        event_id = querylist[1]
    except IndexError:
        pass  # if it doesn't exist then, nvm
    print(msg['from']['first_name'] + "(" + str(from_id) + ") pressed: " + querycommand + " ")
    # if querycommand != "confirmpluschop":  # as long as its not the ending confirm button
    antieventdetails(from_id)  # as long as user press another button when they r supposed to type event details
    antibreakpre_event(from_id)  # they press any stuff before replying to the qns they r supposed reply

    if query_data == "change":
        temp_msg = ""
        for x in range(0, len(PRE_EVENT[from_id][2])):
            temp_msg += "\n" + str(x + 1) + ". " + PRE_EVENT[from_id][2][x]
        try:  # users try to break by spamming
            bot.editMessageText(PRE_EVENT[from_id][0],
                                "Please type in another question" + temp_msg,
                                reply_markup=keypad)
        except:
            pass
        PRE_EVENT[from_id][1] = 1
        return  # terminate to reduce running load

    if query_data == "remove":
        if len(PRE_EVENT[from_id][2]) > 0:
            PRE_EVENT[from_id][2].pop()
            temp_msg = " "
            for x in range(0, len(PRE_EVENT[from_id][2])):
                temp_msg += "\n" + str(x + 1) + ". " + PRE_EVENT[from_id][2][x]
            bot.editMessageText(PRE_EVENT[from_id][0],
                                '<b>' + PRE_EVENT[from_id][
                                    1] + "</b>\n\nWrite in the options you like to provide" + temp_msg,
                                reply_markup=keypad, parse_mode='HTML')
        return  # terminate to reduce running load

    if querycommand == "date" or querycommand == "place":
        foundevent = eventfinder(event_id)

        PRE_EVENT[from_id][2].append(PRE_EVENT[from_id][1])  # store qns temporary storing in list of ans, borrowing
        PRE_EVENT[from_id][2].append(foundevent[0])  # temp store event details also
        if querycommand == "date":
            PRE_EVENT[from_id][1] = -2
            extramsg = "\n<b>Please type in date in the format of YYYY-MM-DD"
        else:
            PRE_EVENT[from_id][1] = -3
            extramsg = "\n<b>Please set the location"
        PRE_EVENT[from_id][2].append(event_id)

        options2 = ["Erase", "Back"]
        optionsent2 = ["erase", "initiate"]
        options4 = ["Set Date", "Set Place"]
        optionsent4 = ["date", "place"]
        options3 = ["Attendance", "Cancel"]
        optionsent3 = ["attend", "cancel"]
        vote = InlineKeyboardMarkup(inline_keyboard=[list(
            map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options2,
                optionsent2)),
            list(
                map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options4,
                    optionsent4)),
            list(
                map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options3,
                    optionsent3)),
            [InlineKeyboardButton(text="Confirm", callback_data=str("confirmpluschop" + '`' + event_id))]])

        locationtext = ""
        if type(WEATHER[event_id][4]) == str:
            locationtext = "\nLocation: " + WEATHER[event_id][4] + "\n"
        temp_msg = "<b>" + foundevent[0] + "\nDate: " + WEATHER[event_id][1] + "\n" + locationtext + WEATHER[event_id][
        3] + "</b>" + foundevent[1]["default"][0] + "\n" + extramsg + "</b>"
        try:  # just to prevent bot errors when there is no change in msg
            bot.editMessageText(foundevent[1][from_id][0], temp_msg, reply_markup=vote, parse_mode='HTML')
        except:
            pass
    if querycommand == 'edit':
        temp_msg = ""
        qns = PRE_EVENT[from_id][1]
        for x in range(0, len(PRE_EVENT[from_id][2])):
            temp_msg += "\n" + str(x + 1) + ". " + PRE_EVENT[from_id][2][x]
        bot.editMessageText(PRE_EVENT[from_id][0],
                            '<b>' + qns + "</b>\n\nWrite in the options you like to provide" + temp_msg,
                            reply_markup=keypad, parse_mode='HTML')
        return  # must terminate

    if querycommand == 'new':
        bot.editMessageText(PRE_EVENT[from_id][0],
                            "Write the question for your event",
                            reply_markup=keypad, parse_mode='HTML')
        PRE_EVENT[from_id][1] = 1  # set 1 to check nxt msg for the qns or not
        PRE_EVENT[from_id][2] = []
        return  # must terminate

    if querycommand == "cont":

        qns = "(No question provided)"
        if type(PRE_EVENT[from_id][1]) == str:  # if qns is provided
            qns = PRE_EVENT[from_id][1]

        temp_msg = ""
        if PRE_EVENT[from_id][2]:  # to check if list is not empty
            temp_msg = ""
            for x in range(0, len(PRE_EVENT[from_id][2])):
                temp_msg += "\n" + str(x + 1) + ". " + PRE_EVENT[from_id][2][x]

        bot.editMessageText(PRE_EVENT[from_id][0],
                            "<b>" + qns + "</b>\n\nWrite in the options you like to provide" + temp_msg,
                            reply_markup=keypad, parse_mode='HTML')

    if querycommand == "abandon":
        event_chatid = telepot.message_identifier(bot.sendMessage(from_id, "Hello"))
        PRE_EVENT[from_id] = [event_chatid, 1, [], []]
        PRE_EVENT[from_id][
            1] = "Meet up next week? Put days free for next week"  # set 1 to check nxt msg for the qns or not
        PRE_EVENT[from_id][2] = ["Mon", "Tue", "Wed", "Thurs", "Fri", "Sat", "Sun"]

        temp_msg = ""
        for x in range(0, len(PRE_EVENT[from_id][2])):
            temp_msg += "\n" + str(x + 1) + ". " + PRE_EVENT[from_id][2][x]

        options = ["Use default", "Edit"]
        optionsent = ["confirm", "edit"]

        vote = InlineKeyboardMarkup(inline_keyboard=[list(
            map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d)), options, optionsent)),
            [InlineKeyboardButton(text="New", callback_data="new")]])
        bot.editMessageText(event_chatid, "<b>Default Settings:</b>\n" + PRE_EVENT[from_id][1] + temp_msg,
                            reply_markup=vote, parse_mode='HTML')
        return  # terminate

    if query_data == "confirm":

        if not PRE_EVENT[from_id][2]:  # means no ans/qns is provided at all/the list of ans is empty
            warning = "\n<b>Fill add in at least one option</b>"
            qns = ""
            if type(PRE_EVENT[from_id][1]) == str:
                qns = PRE_EVENT[from_id][1]
            textrefresh('<b>' + qns + "</b>\n\nWrite in the options you like to provide" + warning,
                        PRE_EVENT[from_id], PRE_EVENT[from_id][0], from_id, keypad, "HTML")

            return  # terminate so it doesnt run
        # PRE_EVENT[from_id][3].append(InlineQueryResultArticle(
        #     id=str(PRE_EVENT[from_id][0]),
        #     title=PRE_EVENT[from_id][1],
        #     input_message_content=InputTextMessageContent(
        #         message_text=PRE_EVENT[from_id][1] + "\nClick button below to choose"
        #     )
        # ))
        DATABASE[event_id_format(PRE_EVENT[from_id][0])] = deepcopy([PRE_EVENT[from_id][1], PRE_EVENT[from_id][2]])
        # store inside database in case if users want make multiple events
        # deepcopy so that u make sure every element in each list is standalone and not connected

        # payload = msg['from']['username']
        payload = event_id_format(PRE_EVENT[from_id][0])
        try:
            if len(DEEP_LINK[payload]) != 0:
                pass
        except (KeyError, ValueError):
            DEEP_LINK[payload] = []
            DEEP_LINK[payload].append(from_id)
        options = ["Send to group chat"]
        optionsent = [PRE_EVENT[from_id][1]]
        templist = list(
            map(lambda c, d: InlineKeyboardButton(text=str(c),
                                                  url='https://telegram.me/meetlehbot?startgroup=%s' % payload),  # needs to change according to bot name
                options, optionsent))
        templist.append(InlineKeyboardButton(text="Start another",
                                             callback_data='reset'))
        # weird way of doing, cus couldnt find a workaround to make buttons in same row

        confirmpad = InlineKeyboardMarkup(
            inline_keyboard=[
                templist
            ])

        temp_msg = ""
        for x in range(0, len(PRE_EVENT[from_id][2])):
            temp_msg += "\n" + str(x + 1) + ". " + PRE_EVENT[from_id][2][x]

        textrefresh('<b>' + PRE_EVENT[from_id][1] + '</b>' + temp_msg, PRE_EVENT[from_id], PRE_EVENT[from_id][0],
                    from_id, confirmpad, 'HTML')
        PRE_EVENT[from_id][1] = 0  # to reset whole thing, status of not adding in options
        PRE_EVENT[from_id][2] = []  # empty all the options
        return  # terminate to reduce running load

    if query_data == "reset":
        PRE_EVENT[from_id][2] = []  # resetting the qns
        event_chatid = telepot.message_identifier(bot.sendMessage(from_id, "Write the question for your event"))
        PRE_EVENT[from_id][0] = event_chatid
        PRE_EVENT[from_id][1] = 1  # set 1 to check nxt msg for the qns or not
        return  # terminate to reduce running load

        # if query_data == adminvotechoice
        # publish final event
        # if query_data == uservotedays
        # add into data which days each user choose

    if querycommand == "confirmevent":
        # remove all other chats
        foundevent = eventfinder(event_id)
        try:  # try cus ppl spam which causess error in console
            bot.deleteMessage(foundevent[3])  # delete first original deeplink post into chat
            foundevent[3] = -1  # to indicate end of voting
        except:
            pass
        # at least one member in the keys
        for user in foundevent[1].keys():
            # make sure u r not edit message for default, cus no updateod
            # update for non-admin side
                if user != from_id and user != "default":
                    try:  # if it doesnt exist
                        bot.editMessageText(foundevent[1][user][0], nonadminchat(event_id, user), parse_mode="HTML")  # update for non-admins
                    except:  # can't figure out which exception to use
                        pass

        # Update for admin

        options = ["Attendance", "Cancel"]
        optionsent = ["attend", "cancel"]
        vote = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text="Initiate event", callback_data=str("initiate" + '`' + event_id))], list(
            map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options,
                optionsent))])
        try:  # try to prevent spam/errors in console because telegram is too slow
            bot.editMessageText(foundevent[1][from_id][0], adminchat(event_id), reply_markup=vote, parse_mode='HTML')
        except:
            pass
        return  # terminate to reduce running load

    if querycommand == "choice":
        foundevent = eventfinder(event_id)
        options = DATABASE[removegrpid(event_id)][1]
        optionsent = []
        for element in options:
            optionsent.append(element + str(options.index(element)))

        for y in optionsent:
            if querylist[2] == y:  # XOR for the choice of each user
                foundevent[1][from_id][optionsent.index(y) + 1] += 1
                if foundevent[1][from_id][optionsent.index(y) + 1] > 1:
                    foundevent[1][from_id][optionsent.index(y) + 1] = 0
                # update for non-admin side

                vote = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(
                        text=str(c), callback_data=str("choice" + '`' + event_id + '`' + d)), options, optionsent))])

                admin_id = foundevent[2]
                if admin_id != from_id:
                    bot.editMessageText(foundevent[1][from_id][0], nonadminchat(event_id, from_id), reply_markup=vote, parse_mode='HTML')
                    # update for non-admins
                # admin side
                vote = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c),
                                                          callback_data=str("choice" + '`' + event_id + '`' + d)),
                        options, optionsent)),
                    [InlineKeyboardButton(text="Confirm Event", callback_data='confirmevent' + '`' + event_id)]])

                try:  # cus if admin haven join yet, then its not in the key and will lead to error and at same time
                    # we dont need update admin side one since he not inside
                    bot.editMessageText(foundevent[1][admin_id][0], adminchat(event_id), reply_markup=vote, parse_mode='HTML')
                # update on admin only
                except:
                    pass
        return  # terminate to reduce running load

    if querycommand == "attend":
        foundevent = eventfinder(event_id)
        options = DATABASE[removegrpid(event_id)][1]
        options2 = ["Initiate event", "Cancel"]
        optionsent2 = ["initiate", "cancel"]

        vote = InlineKeyboardMarkup(inline_keyboard=[list(
            map(lambda c: InlineKeyboardButton(text=str(c),
                                               callback_data=str("checkattend" + '`' + event_id + '`' + c)),
                options)),
            list(
                map(lambda c, d: InlineKeyboardButton(text=str(c),
                                                      callback_data=str(d + '`' + event_id)), options2, optionsent2))])

        bot.editMessageText(foundevent[1][from_id][0], adminchat(event_id) + "\n\n<b>Choose to see attendance</b>",
                            reply_markup=vote, parse_mode='HTML')
        return  # terminate to reduce running load

    if querycommand == "checkattend":
        foundevent = eventfinder(event_id)
        options2 = ["Back", "Cancel"]
        optionsent2 = ["attend", "cancel"]
        vote = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Initiate event",
                                                                           callback_data=str(
                                                                               "initiate" + '`' + event_id))],
                                                     list(
                                                         map(lambda c, d: InlineKeyboardButton(text=str(c),
                                                                                               callback_data=str(
                                                                                                   d + '`' + event_id)),
                                                             options2,
                                                             optionsent2))])

        temp_msg, namelist = attendancefinder(querylist[1], querylist[2])
        bot.editMessageText(foundevent[1][from_id][0], "<b>Attendance for \"" + querylist[2] + "</b>\"" + temp_msg,
                            reply_markup=vote, parse_mode='HTML')
        return  # terminate to reduce running load

    if querycommand == "cancel":
        foundevent = eventfinder(event_id)
        bot.editMessageText(foundevent[1][from_id][0], adminchat(event_id) + "\n\nThank you for using this bot", parse_mode='HTML')
        lst = list(event_id.split('_'))
        try:
            grp_id = int(lst[1])
        except KeyError:
            pass

        del EVENT[grp_id][event_id]  # memory clear and so that can be reused
        del DEEP_LINK[event_id]
        return  # terminate to reduce running load

    if querycommand == "end":
        foundevent = eventfinder(event_id)

        users_list = []
        temp_msg = '<b>' + foundevent[0] + '</b>\n'  # the details
        for user in foundevent[1].keys():
            if user != "default" and foundevent[1][user][1] >= 1:  # means he join
                users_list.append(user)
                temp_msg += '\n' + NAMES[user]
                if foundevent[1][user][1] == 2:  # plus he confirmed
                    temp_msg += "👌🏽"  # add okay emoji

        if not users_list:  # means empty
            temp_msg += '(No one going)'
        foundevent[1]["default"] = [temp_msg, users_list]

        temp_msg += "\n\nThank you for using this bot"

        try:  # just to prevent bot errors when there is no change in msg
            # need edit main grp chat
            bot.editMessageText(foundevent[3], temp_msg , reply_markup=None,
                                parse_mode='HTML')  # main msg need to be updated too
        except:
            pass
        for user in foundevent[1].keys():
            try:  # just to prevent bot errors when there is no change in msg
                # and for everyone's chat
                bot.editMessageText(foundevent[1][user][0], temp_msg, reply_markup=None, parse_mode='HTML')
            except:
                pass
        # then delete the necessary data structures
        lst = list(event_id.split('_'))
        try:
            grp_id = int(lst[1])
        except KeyError:
            pass

        del EVENT[grp_id][event_id]  # memory clear and so that can be reused
        del DEEP_LINK[event_id]
        return  # must terminate

    if querycommand == "initiate":
        foundevent = eventfinder(event_id)
        options = DATABASE[removegrpid(event_id)][1]
        options2 = ["Attendance", "Cancel"]
        optionsent2 = ["attend", "cancel"]

        vote = InlineKeyboardMarkup(inline_keyboard=[list(
            map(lambda c: InlineKeyboardButton(
                text=str(c), callback_data=str("pick" + '`' + event_id + '`' + c)), options)),
            list(
                map(lambda c, d: InlineKeyboardButton(
                    text=str(c), callback_data=str(d + '`' + event_id)), options2, optionsent2))])
        try:  # ppl try to break, if no change in text?
            bot.editMessageText(foundevent[1][from_id][0], adminchat(event_id) + "\n\n<b>Please pick one option</b>",
                                reply_markup=vote, parse_mode='HTML')
        except:
            pass
        return  # terminate to reduce running load

    if querycommand == "pick" or querycommand == "erase":
        foundevent = eventfinder(event_id)
        if querycommand == "erase":
            foundevent[0] = " "
        else:  # means its pick
            foundevent[0] = DATABASE[removegrpid(event_id)][0]  # set to default qns
            foundevent[0] += '\n' + querylist[2] + ":"
        options2 = ["Erase", "Back"]
        optionsent2 = ["erase", "initiate"]
        options4 = ["Set Date", "Set Place"]
        optionsent4 = ["date", "place"]
        options3 = ["Attendance", "Cancel"]
        optionsent3 = ["attend", "cancel"]
        vote = InlineKeyboardMarkup(inline_keyboard=[list(
            map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options2,
                optionsent2)),
            list(
                map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options4,
                    optionsent4)),
            list(
                map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options3,
                    optionsent3)),
            [InlineKeyboardButton(text="Confirm", callback_data=str("confirmpluschop" + '`' + event_id))]])

        PRE_EVENT[from_id][2].append(PRE_EVENT[from_id][1])  # store qns temporary storing in list of ans, borrowing
        PRE_EVENT[from_id][2].append(foundevent[0])  # temp storing the eventdetails as well
        PRE_EVENT[from_id][1] = -1
        PRE_EVENT[from_id][2].append(event_id)  # temporary store the event.id into the last element

        if querycommand != "erase":
            try:
                foundevent[1]["default"][0], foundevent[1]["default"][1] = attendancefinder(querylist[1], querylist[2])
                # reuse "default"
            except:
                foundevent[1]["default"] = [0] * 2
                foundevent[1]["default"][0], foundevent[1]["default"][1] = attendancefinder(querylist[1], querylist[2])

        # textrefresh(foundevent[0] + foundevent[1]["default"][0] + "\n\n<b>Type in the event details</b>",
        #             foundevent[1][from_id], foundevent[1][from_id][0], from_id, vote, 'HTML')
        locationtext = ""
        if type(WEATHER[event_id][4]) == str:
            locationtext = "\nLocation: " + WEATHER[event_id][4] + "\n"

        temp_msg = "<b>" + foundevent[0] + "\nDate: " + WEATHER[event_id][1] + "\n" + locationtext + WEATHER[event_id][
        3] + "</b>\n" + foundevent[1]["default"][0] + "\n\n<b>Type in the event details</b>"
        try:  # just to prevent bot errors when there is no change in msg
            bot.editMessageText(foundevent[1][from_id][0], temp_msg, reply_markup=vote, parse_mode='HTML')
        except:
            pass
        return  # terminate to reduce running load

    if querycommand == "confirmpluschop":
        foundevent = eventfinder(event_id)
        locationtext = ""
        if type(WEATHER[event_id][4]) == str:
            locationtext = "\nLocation: " + WEATHER[event_id][4] + "\n"
        temp_msg = "<b>" + foundevent[0] + "\nDate: " + WEATHER[event_id][1] + "\n" + locationtext + WEATHER[event_id][
        3] + "</b>\n" + foundevent[1]["default"][0]  # whoever is going

        bot.deleteMessage(foundevent[1][from_id][0])  # delete admin options tab first, so no multiple inputs

        options = ["Join", "Confirm", "Leave"]
        optionsent = ["join", "assure", "leave"]
        vote = InlineKeyboardMarkup(inline_keyboard=[list(
            map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options,
                optionsent))])
        foundevent[3] = telepot.message_identifier(bot.sendMessage(DEEP_LINK[event_id][1], temp_msg,
                                                                   reply_markup=vote, parse_mode='HTML'))
        # post in group
        # for admin side
        for user in foundevent[1].keys():
            if user != "default" and user not in foundevent[1]["default"][1]:  # for people not inside
                foundevent[1][user][1] = 0
                options2 = ["Join"]
                optionsent2 = ["join"]
                vote2 = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options2,
                        optionsent2))])

                foundevent[1][user][0] = telepot.message_identifier(bot.sendMessage(user, temp_msg,
                                                                                    reply_markup=vote2,
                                                                                    parse_mode='HTML'))
            elif user != "default":  # for people in the thing already
                foundevent[1][user][1] = 1
                options3 = ["Confirm", "Leave"]
                optionsent3 = ["assure", "leave"]
                vote3 = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options3,
                        optionsent3))])

                foundevent[1][user][0] = telepot.message_identifier(bot.sendMessage(user, temp_msg,
                                                                                    reply_markup=vote3,
                                                                                    parse_mode='HTML'))
                # for user side
        return  # terminate to reduce running load

    if querycommand in ["join", "assure", "leave"]:
        if removegrpid(event_id) in DATABASE.keys():
            attendanceupdater(event_id, from_id, querycommand)
        else:
            print(msg['from']['first_name'] + "(" + str(from_id) + ") pressing on old events that is not saved in database ")
        return


def linking(msg, payload):
    content_type, chat_type, chat_id = telepot.glance(msg)
    global DEEP_LINK

    if any(payload in x for x in list(DEEP_LINK.keys())):
        x = DEEP_LINK[payload][0]  # get the admin id
    #     if chat_id not in DEEP_LINK[payload]:
    #         DEEP_LINK[payload].append(chat_id)
    # else:
    #     pass
        DEEP_LINK[payload + '_' + str(chat_id)] = [x, chat_id]  # then create another eventid that includes the grpid


def removegrpid(event_id_grp_id):  #modify the new event_id with grpid to remove grp_id to get the univ event_id
    lst = list(event_id_grp_id.split('_'))
    return lst[0]


def textrefresh(textmsg, contain_chat_list, chat_id, user_id, markup, parsing):
    global CHATCOUNT
    try:
        CHATCOUNT[user_id] += 1
    except KeyError:
        CHATCOUNT[user_id] = 1
    if CHATCOUNT[user_id] >= 3:
        CHATCOUNT[user_id] = 0
        i = contain_chat_list.index(chat_id)
        bot.deleteMessage(chat_id)
        contain_chat_list.pop(i)
        new_chat_id = telepot.message_identifier(
            bot.sendMessage(user_id, textmsg, reply_markup=markup, parse_mode=parsing))
        contain_chat_list.insert(i, new_chat_id)
        return
    else:
        try:  # just to prevent bot errors when there is no change in msg
            bot.editMessageText(chat_id, textmsg, reply_markup=markup, parse_mode=parsing)
        except:
            pass
        return


def event_id_format(event_code):
    return (((str(event_code).replace("(", "")).replace(")", "")).replace(",", "-")).replace(" ", "")
    # remove all the space, and brackets, and commas and convert to string
    # and put a dash in between the user id


def check_votes(event_id):
    global EVENT
    global DEEP_LINK
    grp_id = DEEP_LINK[event_id][1]
    votes_list = []
    for x in range(0, len(EVENT[grp_id][event_id][1]["default"])):
        i = 0
        for user in EVENT[grp_id][event_id][1].keys():
            if user != "default":
                i += EVENT[grp_id][event_id][1][user][x + 1]
        votes_list.append(i)
    return votes_list


def eventfinder(event_id):
    global DEEP_LINK
    global EVENT
    try:
        return EVENT[DEEP_LINK[event_id][1]][event_id]
    except KeyError:
        print("Cannot find grp_id in DEEP_LINK for " + event_id + " ")  # Debug msg
        return -1


def adminchat(event_id):
    global DATABASE
    foundevent = eventfinder(event_id)
    temp_msg = '<b>' + DATABASE[removegrpid(event_id)][0] + '</b>'  # question
    votes_list = check_votes(event_id)
    for x in range(0, len(foundevent[1]["default"])):
        ans = DATABASE[removegrpid(event_id)][1][x]
        temp_msg += '\n' + ans + " : " + str(votes_list[x])
    return temp_msg  # return qns + ans + no. of votes per choice


def nonadminchat(event_id, user_id):
    global DATABASE
    foundevent = eventfinder(event_id)
    temp_msg = " "
    try:  # in case if user not even in the event in first place
        for x in range(0, len(foundevent[1][user_id])):
            if foundevent[1][user_id][x] == 1:
                temp_msg += '\n' + DATABASE[removegrpid(event_id)][1][x - 1]
    except:
        pass
    temp_msg = '<b>' + foundevent[0] + "</b>\nSelected options:" + temp_msg
    return temp_msg


def attendancefinder(event_id, choice):
    global DATABASE
    global NAMES
    foundevent = eventfinder(event_id)
    namelist = []
    for x in range(0, len(DATABASE[removegrpid(event_id)][1])):
        if choice == DATABASE[removegrpid(event_id)][1][x]:
            for user in foundevent[1].keys():
                if user != "default":  # failsafe to check default, cus default got one index less
                    if foundevent[1][user][x + 1] == 1:
                        namelist.append(user)
    temp_msg = " "
    for name in namelist:
        temp_msg += '\n' + NAMES[name]
    return temp_msg, namelist


def attendanceupdater(event_id, user_id, choice):
    global NAMES
    foundevent = eventfinder(event_id)

    choiceoptions = ["leave", "join", "assure"]
    choicenum = choiceoptions.index(choice)

    if user_id not in foundevent[1].keys():  # means user never voted at the start at all
        msg_id = telepot.message_identifier(bot.sendMessage(user_id, "Welcome!"))  # send random msg first
        foundevent[1][user_id] = [msg_id, choicenum]
    else:
        foundevent[1][user_id][1] = choicenum

    users_list = []
    locationtext = ""
    if type(WEATHER[event_id][4]) == str:
        locationtext = "\nLocation: " + WEATHER[event_id][4] + "\n"
    temp_msg = "<b>" + foundevent[0] + "\nDate: " + WEATHER[event_id][1] + "\n" + locationtext + WEATHER[event_id][
        3] + "</b>\n"  # the details
    for user in foundevent[1].keys():
        if user != "default" and foundevent[1][user][1] >= 1:  # means he join
            users_list.append(user)
            temp_msg += '\n' + NAMES[user]
            if foundevent[1][user][1] == 2:  # plus he confirmed
                temp_msg += "👌🏽"  # add okay emoji

    if not users_list:  # means empty
        temp_msg += '(No one going)'
    foundevent[1]["default"] = [temp_msg, users_list]

    options = ["Join", "Confirm", "Leave"]
    optionsent = ["join", "assure", "leave"]
    vote = InlineKeyboardMarkup(inline_keyboard=[list(
        map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options,
            optionsent))])

    try:  # just to prevent bot errors when there is no change in msg
        bot.editMessageText(foundevent[3], temp_msg, reply_markup=vote,
                            parse_mode='HTML')  # main msg need to be updated too
    except:
        pass

    # update bot first

    for user in foundevent[1].keys():
        if user != "default":
            user_choice = foundevent[1][user][1]

            if user_choice == 0:  # he choose to leave
                options = ["Join"]
                optionsent = ["join"]

            elif user_choice == 1:  # he choose to join
                options = ["Confirm", "Leave"]
                optionsent = ["assure", "leave"]

            elif user_choice == 2:  # he choose to confirm
                options = ["Unconfirm", "Leave"]
                optionsent = ["join", "leave"]

            vote = InlineKeyboardMarkup(inline_keyboard=[list(
                map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options,
                    optionsent))])

            if user == foundevent[2]:  # if user is admin, different button, cus need one end event button
                vote = InlineKeyboardMarkup(inline_keyboard=[list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options,
                        optionsent)),
                    [InlineKeyboardButton(text='End event', callback_data=str('end' + '`' + event_id))]])
            try:  # just to prevent bot errors when there is no change in msg
                bot.editMessageText(foundevent[1][user][0], temp_msg, reply_markup=vote, parse_mode='HTML')
            except:
                pass


def antieventdetails(user_id):  # checker to see if they decide to screw things up when they r asked from event details
    global PRE_EVENT

    try:
        if PRE_EVENT[user_id][1] <= -1:  # means they were trying to rewrite a new event detail yet /createevent
            event_id = PRE_EVENT[user_id][2].pop()
            foundevent = eventfinder(event_id)  # need to fix the original chat msg which is asking for event details
            foundevent[0] = PRE_EVENT[user_id][2].pop()
            PRE_EVENT[user_id][1] = PRE_EVENT[user_id][2].pop()  # so we return the original data
            # and at same time, edit the original message to show that no event details is given

            options2 = ["Erase", "Back"]
            optionsent2 = ["erase", "initiate"]
            options4 = ["Set Date", "Set Place"]
            optionsent4 = ["date", "place"]
            options3 = ["Attendance", "Cancel"]
            optionsent3 = ["attend", "cancel"]
            vote = InlineKeyboardMarkup(inline_keyboard=[list(
                map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options2,
                    optionsent2)),
                list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options4,
                        optionsent4)),
                list(
                    map(lambda c, d: InlineKeyboardButton(text=str(c), callback_data=str(d + '`' + event_id)), options3,
                        optionsent3)),
                [InlineKeyboardButton(text="Confirm", callback_data=str("confirmpluschop" + '`' + event_id))]])

            if PRE_EVENT[user_id][1] == -1:  # if the user is specifically asked for event details only
                foundevent[0] = "(No details given)"

            locationtext = ""
            if type(WEATHER[event_id][4]) == str:
                locationtext = "\nLocation: " + WEATHER[event_id][4] + "\n"

            bot.editMessageText("<b>" + foundevent[0] + "\nDate: " + WEATHER[event_id][1] + "\n" + locationtext + WEATHER[event_id][
                                3] + "</b>\n" + foundevent[1]["default"][0], reply_markup=vote, parse_mode='HTML')
    except:
        pass


def antibreakpre_event(user_id):
    global PRE_EVENT
    try:  # in case if they r not in the user_id at all
        if PRE_EVENT[user_id][1] == 1:  # when they r supposed to fill up another new qns for PREEVENT
            PRE_EVENT[user_id][1] = "(No question provided)"
    except:
        pass


TOKEN = ''
bot = telepot.Bot(TOKEN)

MessageLoop(bot, {'chat': on_chat_message,
                  # 'chosen_inline_result': on_chosen_inline_result,
                  'callback_query': on_callback_query}).run_as_thread()
print("Listening.. ")
while 1:
    time.sleep(10)
    f = open('store.p', 'wb')
    pickle.dump([PRE_EVENT, EVENT, DATABASE, DEEP_LINK, USEREVENTS, NAMES, CHATCOUNT, WEATHER], f)
    f.close()



