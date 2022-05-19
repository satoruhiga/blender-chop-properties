import os
import sys

PATH = os.path.join(os.path.dirname(__file__), 'site-packages')
if not PATH in sys.path:
    sys.path.append(PATH)

bl_info = {
	"name": "CHOP Properties",
	"author": "satoruhiga",
	"version": (1, 0),
	"blender": (3, 0, 0),
	"location": "Properties > Scene Properties > CHOP Properties",
	"description": "",
	"warning": "",
	"support": "COMMUNITY",
	"wiki_url": "",
	"tracker_url": "",
	"category": "Animation"
}

###

import re

class Channel:
    def __init__(self, name, samples):
        self.name = name
        self.samples = samples
    
class Clip:
    def __init__(self):
        self.rate = 30
        self.start = 0
        self.tracklength = 0
        self.channels = []

    def appendChan(self, name):
        c = Channel(name, [0] * self.tracklength)
        self.channels.append(c)
        return c
    
    def open(self, path):
        q = re.compile('(\w+)\s=\s(.*)')
        fp = open(path, 'r')

        level = 0
        
        self.rate = 30
        self.start = 0
        self.tracklength = 0
        self.channels = []

        self._channel = None
        
        def push_params(key, data):
            if level == 1:
                if key == 'start':
                    self.start = int(float(data))
                elif key == 'tracklength':
                    self.tracklength = int(float(data))
                elif key == 'rate':
                    self.rate = float(data)
            elif level == 2:
                if key == 'name':
                    self._channel = self.appendChan(data)
                elif key == 'data' or key == 'data_rle':
                    arr = data.split(' ')
                    arr_index = 0
                    it = iter(arr)

                    try:
                        while True:
                            x = next(it)
                            if x[0] == '@':
                                v = next(it)
                                for i in range(int(x[1:])):
                                    self._channel.samples[arr_index] = float(v)
                                    arr_index += 1
                            else:
                                self._channel.samples[arr_index] = float(x)
                                arr_index += 1

                    except StopIteration:
                        pass

        for line in fp:
            line = line.strip()
            
            if line == '{':
                level += 1
            elif line == '}':
                level -= 1
            else:		
                m = q.search(line)
                
                if m:
                    g = m.groups()
                    push_params(g[0], g[1])

    def save(self, path):
        fp = open(path, 'w')
        
        fp.write('{\n')
        fp.write(' rate = ' + str(self.rate) + '\n')
        fp.write(' start = ' + str(self.start) + '\n')
        fp.write(' tracklength = ' + str(self.tracklength) + '\n')
        fp.write(' tracks = ' + str(len(self.channels)) + '\n')
    
        for c in self.channels:
            fp.write(' {\n')
            fp.write('  name = ' + c.name + '\n')
            fp.write('  data = ' + " ".join(map(str, c.samples)) + '\n')
            fp.write(' }\n')
            
        fp.write('}')
    
        fp.close()

###

import bpy
import os

class ClearCustomPropsOperator(bpy.types.Operator):
    bl_idname = "chop_props.clear_custom_props"
    bl_label = "NOP"

    def execute(self, context):
        sc = context.scene
        keys = [x for x in sc.keys()]

        arr = []
        for fc in sc.animation_data.action.fcurves:
            for k in keys:
                if k in fc.data_path:
                    arr.append(fc)
        
        for x in arr:
            sc.animation_data.action.fcurves.remove(x)

        for x in keys:
            n = str(x)
            if n.startswith('chan_'):
                del sc[n]

        return {'FINISHED'}


class LoadClipOperator(bpy.types.Operator):
    bl_idname = "chop_props.import_file"
    bl_label = "NOP"

    def execute(self, context):
        scene = context.scene

        p = bpy.path.abspath(scene.chop_props.filepath)
        if not os.path.exists(p):
            return {'CANCELLED'}

        c = Clip()
        c.open(p)

        # clear all keyframes
        for x in c.channels:
            prop_name = 'chan_%s' % x.name
            if prop_name in scene.keys():
                del scene[prop_name]

        frame_current = bpy.context.scene.frame_current

        # insert new keyframes
        for i in range(0, c.tracklength):
            bpy.context.scene.frame_set(i)
            
            for x in c.channels:
                prop_name = 'chan_%s' % x.name
                scene[prop_name] = x.samples[i]

                scene.keyframe_insert(data_path=f'["{prop_name}"]')

        bpy.context.scene.frame_set(frame_current)
        
        return {'FINISHED'}


class UpdateDependenciesOperator(bpy.types.Operator):
    bl_idname = "chop_props.update_dependencies"
    bl_label = "NOP"

    def execute(self, context):
        collections = ["scenes", "objects", "meshes", "materials", "textures",
            "speakers", "worlds", "curves", "armatures", "particles", "lattices", 
            "shape_keys", "cameras"]

        for col in collections:
            collection = eval("bpy.data.%s"%col)
            for ob in collection:
                if ob.animation_data is not None:
                    for driver in ob.animation_data.drivers:
                        driver.driver.expression = str(driver.driver.expression)

        return {'FINISHED'}


class LoadClipPanel(bpy.types.Panel):
    bl_label = "CHOP Properties"
    bl_idname = "SCENE_PT_chop_props"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout

        scene = context.scene

        box = layout.box()
        box.label(text="OSC Input")

        sp = box.split(align=True, factor=0.3)
        sp.prop(scene.chop_props, "osc_active", text="Active")
        sp.prop(scene.chop_props, "osc_port", text="Port")

        row = box.row()
        row.prop(scene.chop_props, "sync_frames", text="Sync Frames to /frame [FRAME]")

        box = layout.box()
        box.label(text="File Input")

        row = box.row()
        row.prop(scene.chop_props, "filepath", text=".clip File")

        row = box.row()
        row.operator(LoadClipOperator.bl_idname, text="Import")

        row = layout.row()
        row.operator(ClearCustomPropsOperator.bl_idname, text="Clear Custom Props")

        row = layout.row()
        row.operator(UpdateDependenciesOperator.bl_idname, text="Update Driver Dependencies")

###

import socket
import pythonosc.osc_packet

g_sock = None
g_context = None

def parse_packet(data):
    global g_context
    scene = g_context.scene

    pkt = pythonosc.osc_packet.OscPacket(data)
    
    for msg in pkt.messages:
        addr = msg.message.address[1:]
        value = msg.message.params[0]

        if addr.startswith('_'):
            continue
        
        if addr == 'frame':
            if scene.chop_props.sync_frames:
                scene.frame_set(value)
        else:
            prop_name = f'chan_{addr}'
            scene[prop_name] = value
        

def timer_callback():
    global g_sock
    global g_context

    if g_sock:
        try:
            while True: 
                buf = g_sock.recv(4096)
                parse_packet(buf)
            
        except socket.error:
            pass

        g_context.scene.update_tag()
    
    return bpy.context.scene.render.fps_base / bpy.context.scene.render.fps

def start_server(props, context):
    global g_context
    global g_sock

    g_sock = socket.socket(socket.AF_INET, type=socket.SOCK_DGRAM)
    g_sock.setblocking(False)
    g_sock.bind(('0.0.0.0', props.osc_port))

    g_context = context

    if not bpy.app.timers.is_registered(timer_callback):
        bpy.app.timers.register(timer_callback)


def stop_server(props, context):
    global g_context
    global g_sock

    if bpy.app.timers.is_registered(timer_callback):
        bpy.app.timers.unregister(timer_callback)

    g_context = None

    if g_sock:
        g_sock.close()
        g_sock = None

def on_osc_active(props, context):
    stop_server(props, context)

    if props.osc_active:
        start_server(props, context)

def on_osc_port(props, context):
    stop_server(props, context)

    if props.osc_active:
        start_server(props, context)

###

class ChopPropertyGroup(bpy.types.PropertyGroup):
    sock: None
    osc_active: bpy.props.BoolProperty(name='OSC Active', default=False, update=on_osc_active)
    osc_port: bpy.props.IntProperty(name='OSC Port', default=10000, update=on_osc_port)
    sync_frames: bpy.props.BoolProperty(name='Sync Frames', default=False)
    filepath: bpy.props.StringProperty(name='File Path', subtype='FILE_PATH')

###

classes = (
    ChopPropertyGroup,
    LoadClipPanel,
    LoadClipOperator,
    ClearCustomPropsOperator,
    UpdateDependenciesOperator,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.chop_props = bpy.props.PointerProperty(type=ChopPropertyGroup)

def unregister():
    del bpy.types.Scene.chop_props

    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
