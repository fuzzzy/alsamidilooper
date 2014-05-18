# -*- coding: utf-8 -*-
# <nbformat>3.0</nbformat>

# <codecell>

def log_console(string_message):
    print(string_message)

# <codecell>

class MidiMessage:
    MIDI_NOTE_ON = 1
    MIDI_NOTE_OFF = 2
    MIDI_CC = 3
    MIDI_START = 4
    MIDI_STOP = 5
    MIDI_CONTINUE = 6
    MIDI_TICK = 7
    MIDI_OTHER = 8
    
    message = 0
    param1 = -1
    param2 = -1
    tick =-1
    msgType = MIDI_OTHER
    
    def __init__(self, timestamp, messageType, param1val=-1, param2val=-1):
        self.message = messageType
        self.param1 = param1val
        self.param2 = param2val
        self.tick = timestamp
        if (messageType / 0x10) == 0x8:
            self.msgType = MidiMessage.MIDI_NOTE_OFF
        elif (messageType / 0x10) == 0x9:
            self.msgType = MidiMessage.MIDI_NOTE_ON
        elif (messageType / 0x10) == 0xB:
            self.msgType = MidiMessage.MIDI_CC
        elif (messageType) == 0xFA:
            self.msgType = MidiMessage.MIDI_START
        elif (messageType) == 0xFC:
            self.msgType = MidiMessage.MIDI_STOP
        elif (messageType) == 0xFB:
            self.msgType = MidiMessage.MIDI_CONTINUE
        elif (messageType) == 0xF8:
            self.msgType = MidiMessage.MIDI_TICK
        else:
            self.msgType = MidiMessage.MIDI_OTHER   

    @staticmethod
    def createMessageFromBytearray(timestamp, data):
        message = None
        if len(data) == 1 :
            message = MidiMessage(timestamp, data[0])
        elif len(data) == 2:
            message = MidiMessage(timestamp, data[0], data[1])
        elif len(data) == 3:
            message = MidiMessage(timestamp, data[0], data[1], data[2]) 
        return message
    
    def getType(self):
        return self.msgType
    
    def __str__(self):
        return str(self.msgType) + " " + str(self.tick)+ " " + hex(self.message) + " " + hex(self.param1) + " " + hex(self.param2)
    
    def toBytes(self):
        bytes = None
        if (self.msgType == MidiMessage.MIDI_NOTE_OFF) or (self.msgType == MidiMessage.MIDI_NOTE_ON) or (self.msgType == MidiMessage.MIDI_CC):
            bytes = [self.message, self.param1, self.param2]
        
        return "".join(map(chr, bytes))

# <codecell>

class ControlsProcessor:
    start_playback = None
    start_record = None
    
    REC_BTN_CC = 0xb
    PLAY_BTN_CC = 0xe
    
    def __init__(self, start_playback_delegate, start_record_delegate):
        self.start_playback = start_playback_delegate
        self.start_record = start_record_delegate
        
    def processInput(self, message):
        if message.msgType == MidiMessage.MIDI_CC:
            if message.param1 == ControlsProcessor.REC_BTN_CC:
                self.start_record()
            elif message.param1 == ControlsProcessor.PLAY_BTN_CC:
                self.start_playback()
    

# <codecell>

class MidiClock:
    tick = 0
    isPlaying = False
    
    stop_delegate = None
    bar_delegate = None
    tick_delegate = None 
    
    def __init__(self, tick_delegat, bar_start_delegate, stop_dlgt):
        self.bar_delegate = bar_start_delegate
        self.tick_delegate = tick_delegat
        self.stop_delegate = stop_dlgt
    
    def processInput(self, message):
        if message.msgType == MidiMessage.MIDI_TICK:
            if(self.isPlaying) :
                self.tick = self.tick + 1
                self.tick_delegate()
                if (self.tick % 96) == 0:
                    self.bar_delegate()

        elif message.msgType == MidiMessage.MIDI_START:
            self.bar_delegate()
            self.tick = 0
            self.isPlaying = True
            log_console("Got clock!..")
        elif message.msgType == MidiMessage.MIDI_CONTINUE:
            self.isPlaying = True
        elif message.msgType == MidiMessage.MIDI_STOP:
            self.isPlaying = False
            self.stop_delegate()
        
    def getBars(self):
        return ticks % 96

# <codecell>

class Sequencer:
    clock = 0
    recStart = 0
    loopLen = 0
    outputFD = None
    sendPlayedNoteThrough = False
    
    sequence = None
    pending_start = None
    pending_end = None
    
    STATE_REC = 0x5122
    STATE_PLAY = 0x5123
    STATE_IDLE = 0x5124
    STATE_WAITING_FOR_REC = 0x5125
    STATE_WAITING_FOR_PLAY = 0x5126
    STATE_WAITING_FOR_PLAY_AFTER_REC = 0x5127 #we're still recording
    STATE_WAITING_FOR_STOP = 0x5128
    
    BAR_LENGTH_IN_TICKS = 96 
    SYNC_THRESHOLD = 7
    
    state = STATE_IDLE
    
    def __init__(self, output_device_fd, loopedIsPlaying):
        self.outputFD = output_device_fd
        self.sequence = dict()
        self.pending_start = []
        self.pending_end = []
        self.sendPlayedNoteThrough = not loopedIsPlaying
    
    def appendMessage(self, time, message):
        if time in self.sequence:
            # append the new number to the existing array at this slot
            self.sequence[time].append(message)
            #log_console("note added 2 tick: " + str(time) + " msg: " +   str(message))
        else:
            #add new list, so may be there are more than one note on tick
            msgs = [message]
            self.sequence[time] = msgs
            #log_console ("note added tick: " + str(time) + " msg: " +   str(message))
    
    def appendPending(self, msg_list):
        for msg in msg_list:
            self.appendMessage(msg.time, msg)
            log_console("appended pending at: " + str(msg.time))
        del msg_list[:]
            
    def processInput(self, message):
        #log_console ("got note: " + str(message) + " clock: " + str(self.clock))
        if(self.state == Sequencer.STATE_REC ) or (self.state == Sequencer.STATE_WAITING_FOR_PLAY_AFTER_REC):
            time = self.clock - self.recStart
            self.appendMessage(time, message)
        else:
            #we're not recording yet, bu lets keep track of played notes, 
            # so if player misses bar start, we recover them
            time = self.clock % Sequencer.BAR_LENGTH_IN_TICKS
            if (time < Sequencer.SYNC_THRESHOLD):
                message.time = time
                self.pending_start.append(message)
            elif(time == Sequencer.SYNC_THRESHOLD):
                del self.pending_start[:]
                log_console("pending_start cleared")
            elif(time == (Sequencer.BAR_LENGTH_IN_TICKS - Sequencer.SYNC_THRESHOLD)):
                del self.pending_end[:]
                log_console("pending_end cleared")
            elif (Sequencer.BAR_LENGTH_IN_TICKS - time) < (Sequencer.SYNC_THRESHOLD * 2):
                message.time = 0
                self.pending_end.append(message)
        
        if self.sendPlayedNoteThrough:
            self.outputMessage(message)
        
    def outputMessage(self, msg):
        os.write(self.outputFD, msg.toBytes())
        #log_console("playing: " + str(msg))
    
    def reset_clock(self):
        self.clock = 0
        del self.pending_start[:]
        del self.pending_end[:]
    
    def tick(self):
        if(self.clock % Sequencer.BAR_LENGTH_IN_TICKS) == 0:
            if (self.state == Sequencer.STATE_WAITING_FOR_REC):
                self.recStart = self.clock
                self.state = Sequencer.STATE_REC
                self.sequence.clear()
                self.appendPending(self.pending_end)
                del self.pending_start[:]
                log_console("rec started from sync, tick: " + str(self.clock))
            elif (self.state == Sequencer.STATE_WAITING_FOR_PLAY_AFTER_REC):
                self.loopLen = self.clock - self.recStart
                self.state = Sequencer.STATE_PLAY
                log_console("rec stop, play started (sync), tick: " + str(self.clock) + " len: " + str(self.loopLen))
            elif (self.state == Sequencer.STATE_WAITING_FOR_PLAY):
                self.state = Sequencer.STATE_PLAY
                log_console("play started (sync), tick: " + str(self.clock) + " len: " + str(self.loopLen))
            elif (self.state == Sequencer.STATE_WAITING_FOR_STOP): 
                self.state = Sequencer.STATE_IDLE
                log_console("stopped (sync) tick: " + str(self.clock))
                
        if (self.state == Sequencer.STATE_PLAY) and (self.loopLen > 0):
            position = self.clock % self.loopLen
            if position in self.sequence:
                for msg in self.sequence[position]:
                    self.outputMessage(msg) 
                    #log_console("playing seq at pos: " + str(position) + " clock: " + str(self.clock))
                
        self.clock = self.clock + 1
        
    def handleRec(self):
        currentBarPos = (self.clock % Sequencer.BAR_LENGTH_IN_TICKS)
        if ((currentBarPos) < Sequencer.SYNC_THRESHOLD):
            self.state = Sequencer.STATE_REC
            self.recStart = self.clock - currentBarPos
            self.sequence.clear()
            self.appendPending(self.pending_start)
            del self.pending_end[:]
            log_console("rec started, clock: " + str(self.recStart))
        else:
            self.state = Sequencer.STATE_WAITING_FOR_REC
            del self.pending_start[:]
            log_console("preparing for rec at: " + str(self.clock))

    def handleStopRec(self):
        if(self.clock % Sequencer.BAR_LENGTH_IN_TICKS == 0):
            self.state = Sequencer.STATE_PLAY
            self.loopLen = self.clock - self.recStart
            log_console("rec stopped, len: " + str(self.loopLen))
        else:
            self.state = Sequencer.STATE_WAITING_FOR_PLAY_AFTER_REC
            log_console("preparing for stop rec at: " + str(self.clock))
        
        
    def handlePlay(self):
        if(self.clock % Sequencer.BAR_LENGTH_IN_TICKS == 0):
            self.state = Sequencer.STATE_PLAY
            log_console("play started " + str(self.clock))
        else:
            self.state = Sequencer.STATE_WAITING_FOR_PLAY
            log_console("preparing for play at: " + str(self.clock))
    
    def handleStopPlay(self):
        self.state =  Sequencer.STATE_IDLE
        log_console("we're idle at "  + str(self.clock))
    
    def toggleRec(self):
        if Sequencer.STATE_PLAY == self.state:
            self.handleRec()
        elif Sequencer.STATE_IDLE == self.state:
            self.handleRec()
        elif Sequencer.STATE_WAITING_FOR_PLAY == self.state:
            self.handleRec()
        elif Sequencer.STATE_WAITING_FOR_PLAY_AFTER_REC == self.state:
            self.handleRec()
        elif Sequencer.STATE_WAITING_FOR_STOP == self.state:
            self.handleRec()
        elif Sequencer.STATE_REC == self.state:
            self.handleStopRec()
        elif Sequencer.STATE_WAITING_FOR_REC == self.state:   
            self.handlePlay()

    def togglePlay(self):
        if Sequencer.STATE_REC == self.state:
            self.handleStopRec()
        elif Sequencer.STATE_IDLE == self.state:
            self.handlePlay()
        elif Sequencer.STATE_WAITING_FOR_REC == self.state:
            self.handlePlay()
        elif Sequencer.STATE_WAITING_FOR_STOP == self.state:
            self.handlePlay()
        elif Sequencer.STATE_PLAY == self.state:
            self.handleStopPlay()
        #STATE_WAITING_FOR_PLAY_AFTER_REC
        #STATE_WAITING_FOR_PLAY

# <codecell>

import select
import time
import os

def devName(d_name):
    pipe = os.popen('cat /proc/asound/cards | grep ' + d_name).readline()
    x = pipe[1]
    return "/dev/snd/midiC"+x+"D0"
    
class MidiLooper:
    controllerDevice = devName("Interface")#"/dev/snd/midiC1D0" #rw controls
    hostDevice = devName("mio")#"/dev/snd/midiC2D0"       #r clock
    loopedDevice = devName("Y12") #"/dev/snd/midiC2D0"     #rw input, send clock
    playbackDevice = devName("Y12") #"/dev/snd/midiC2D0"   #w output
    
    #loopedDevice = devName("mio") #"/dev/snd/midiC2D0"     #rw input, send clock
    #playbackDevice = devName("mio") #"/dev/snd/midiC2D0"   #w output
    
    controllerFD = None
    hostFD = None
    loopedFD = None
    playbackFD = None
    
    controls = None
    clock = None
    seq = None
    
    
        
    def toggleRec(self):
        self.seq.toggleRec()
        
    def togglePlay(self):
        self.seq.togglePlay()

    def new_bar_started(self):
        idling=1
    
    def tick(self):
        self.seq.tick()
    
    def stopped(self):
        self.seq.reset_clock()
    
    def mainloop(self):
        log_console ("devices:")
        log_console ("controllerDevice: " + self.controllerDevice)
        log_console ("hostDevice: " + self.hostDevice)
        log_console ("loopedDevice: " + self.loopedDevice)
        log_console ("playbackDevice: " + self.playbackDevice)
        
        #setting up interfaces
        self.controls = ControlsProcessor(self.togglePlay, self.toggleRec)
        self.clock = MidiClock(self.tick, self.new_bar_started, self.stopped)
        
        self.controllerFD = os.open(self.controllerDevice, os.O_RDWR)
        self.hostFD = os.open(self.hostDevice, os.O_RDONLY)
        if self.loopedDevice != self.hostDevice:
            self.loopedFD = os.open(self.loopedDevice, os.O_RDONLY)
        self.playbackFD = os.open(self.playbackDevice, os.O_WRONLY)
        
        self.seq = Sequencer(self.playbackFD, self.loopedDevice == self.playbackDevice)
            
        inputs = [self.controllerFD, self.hostFD]
        if not (self.loopedFD is None):
            inputs.append(self.loopedFD)
        outputs = []
        
        continuing = True
        
        while continuing:
            readable, writable, exceptional = select.select(inputs, outputs, inputs)
            if readable:
                for device in readable:
                    if device == self.controllerFD:
                        data = bytearray(os.read(self.controllerFD, 3))
                        message = MidiMessage.createMessageFromBytearray(0, data)
                        #log_console("ctl :" + str(message))
                        if message.param1 == 0x40:
                            continuing = False
                            log_console("stopping...")
                        self.controls.processInput(message)
                        
                    elif device == self.loopedFD:
                        data = bytearray(os.read(self.loopedFD, 3))
                        message = MidiMessage.createMessageFromBytearray(self.clock.tick, data)
                        #log_console("lpd :" + str(message));
                       # if (message.msgType == MidiMessage.MIDI_TICK) or (message.msgType == MidiMessage.MIDI_START) or (message.msgType == MidiMessage.MIDI_CONTINUE) or (message.msgType == MidiMessage.MIDI_STOP):
                       #     self.clock.processInput(message)
                        if (message.msgType == MidiMessage.MIDI_NOTE_ON) or (message.msgType == MidiMessage.MIDI_NOTE_OFF):
                            self.seq.processInput(message)
                            
                    elif device == self.hostFD:
                        data = bytearray(os.read(self.hostFD, 3))
                        message = MidiMessage.createMessageFromBytearray(self.clock.tick, data)
                        #log_console("host :" + str(message))
                        
                        if (message.msgType == MidiMessage.MIDI_TICK) or (message.msgType == MidiMessage.MIDI_START) or (message.msgType == MidiMessage.MIDI_CONTINUE) or (message.msgType == MidiMessage.MIDI_STOP):
                            self.clock.processInput(message)
                        elif (message.msgType == MidiMessage.MIDI_NOTE_ON) or (message.msgType == MidiMessage.MIDI_NOTE_OFF):
                            self.seq.processInput(message)
    
    def cleanup(self):
        self.closeFile(self.controllerFD)
        self.closeFile(self.hostFD)
        self.closeFile(self.loopedFD)
        self.closeFile(self.playbackFD) 
        log_console ("cleaned...")

    def closeFile(self, desc):
        if not (desc is None):
            os.close(desc)
            desc = None
            
    def go(self):
        self.cleanup()
        try:
            self.mainloop()
        finally:
            self.cleanup()

# <codecell>

lpr = MidiLooper()
lpr.go()

# <codecell>


