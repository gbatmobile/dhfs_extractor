import re

def extract_bits(numb, position, tam):
    return (numb >> (position + 1 - tam)) & ((1 << tam) - 1)

class DHFS41:
    def __init__(self, DEBUG=False):
        self.PART_TABLE_OFF = 0x3C00
        self.DESC_SIZE = 32
        self.img_loaded = False
        self.disk      = None
        self.num_parts = 0

        self.DEBUG = DEBUG
        self.config={}
        self.config['DEBUG'] = DEBUG
        self.config['CARVE_SIGNAT'] = re.compile(b"^\x44\x48\x49\x49")

    def get_num_descs(self, part_idx):
        return len(self.all_descs[part_idx]) // self.DESC_SIZE

    def get_desc(self, part_idx, desc_idx):
        off_desc = desc_idx * self.DESC_SIZE
        return self.all_descs[part_idx][off_desc: off_desc+self.DESC_SIZE]

    def get_desc_type(self, part_idx, desc_idx):
        desc = self.get_desc(part_idx, desc_idx)
        return  int.from_bytes(desc[0:1], byteorder='little')

    def get_begin_desc(self, part_idx, desc_idx):
        desc = self.get_desc(part_idx, desc_idx)
        return int.from_bytes(desc[24:28], byteorder='little')

    def get_next_desc(self, part_idx, desc_idx):
        desc = self.get_desc(part_idx, desc_idx)
        return int.from_bytes(desc[12:16], byteorder='little')

    def get_prev_desc(self, part_idx, desc_idx):
        desc = self.get_desc(part_idx, desc_idx)
        return int.from_bytes(desc[20:24], byteorder='little')

    def get_last_desc(self, part_idx, desc_idx):
        # Iterative walk: long chains exceeded Python's recursion limit and
        # a corrupted chain pointing back to itself never ended.
        visited = set()
        while True:
            visited.add(desc_idx)
            nextDesc = self.get_next_desc(part_idx, desc_idx)
            if (nextDesc == 0 or nextDesc == 0xFFFFFFFF or
                    nextDesc >= self.NUM_FRAGS[part_idx] or nextDesc in visited):
                return desc_idx
            desc_idx = nextDesc

    def get_num_frags(self, part_idx, desc_idx):
        if self.get_desc_type(part_idx, desc_idx) == 1:
            desc = self.get_desc(part_idx, desc_idx)
            return int.from_bytes(desc[2:4], byteorder='little') + 1
        else:
            return self.get_num_frags(part_idx,
                            self.get_begin_desc(part_idx, desc_idx))

    def get_frag_number(self, part_idx, desc_idx):
        if self.get_desc_type(part_idx, desc_idx) == 1:
            return 0

        desc = self.get_desc(part_idx, desc_idx)
        return int.from_bytes(desc[2:4], byteorder='little')

    def get_camera(self, part_idx, desc_idx):
        desc = self.get_desc(part_idx, desc_idx)
        return int.from_bytes(desc[1:2], byteorder='little') - 48 + 1

    def decode_timestamp(self, ts):
        return extract_bits(ts, 31, 6), extract_bits(ts, 25, 4), \
               extract_bits(ts, 21, 5), extract_bits(ts, 16, 5), \
               extract_bits(ts, 11, 6), extract_bits(ts, 5, 6)

    def get_timestamps(self, part_idx, desc_idx):
        desc = self.get_desc(part_idx, desc_idx)
        return (int.from_bytes(desc[4:8], byteorder='little'),
                int.from_bytes(desc[8:12], byteorder='little'))

    def get_begin_timestamp(self, part_idx, desc_idx):
        desc = self.get_desc(part_idx, desc_idx)
        return int.from_bytes(desc[4:8], byteorder='little')

    def get_end_timestamp(self, part_idx, desc_idx):
        desc = self.get_desc(part_idx, desc_idx)
        return int.from_bytes(desc[8:12], byteorder='little')

    def get_begin_date(self, part_idx, desc_idx):
        beginTimeStamp = self.get_begin_timestamp(part_idx, desc_idx)
        return self.timestamp_to_date(beginTimeStamp)

    def get_begin_time(self, part_idx, desc_idx):
        timestamp = self.get_begin_timestamp(part_idx, desc_idx)
        return self.timestamp_to_time(timestamp)

    def get_end_time(self, part_idx, desc_idx):
        timestamp = self.get_end_timestamp(part_idx, desc_idx)
        return self.timestamp_to_time(timestamp)

    def timestamp_to_date(self, timestamp):
        year, month, day, _, _, _ = self.decode_timestamp(timestamp)
        return f"20{year:02d}-{month:02d}-{day:02d}"

    def timestamp_to_time(self, timestamp):
        _, _, _, hour, minute, sec = self.decode_timestamp(timestamp)
        return f"{hour:02d}:{minute:02d}:{sec:02d}"

    def timestamp_human(self, timestamp):
        year, month, day, hour, minute, sec = self.decode_timestamp(timestamp)
        return f"20{year:02d}-{month:02d}-{day:02d} "+\
               f"{hour:02d}:{minute:02d}:{sec:02d}"

    def decode_descriptor(self, part_idx, desc_idx):
        dic = {
            'descType'     : self.get_desc_type(part_idx, desc_idx),
            'camera'       : self.get_camera(part_idx, desc_idx),
            'begTime'      : self.timestamp_human(self.get_begin_timestamp(part_idx, desc_idx)),
            'endTime'      : self.timestamp_human(self.get_end_timestamp(part_idx, desc_idx)),
            'numFrag'      : self.get_frag_number(part_idx, desc_idx),
            'totFrags'     : self.get_num_frags(part_idx, desc_idx),
            'beginDesc'    : self.get_begin_desc(part_idx, desc_idx),
            'prevDesc'     : self.get_prev_desc(part_idx, desc_idx),
            'nextDesc'     : self.get_next_desc(part_idx, desc_idx),
            'sizeLast'     : self.get_last_frag_size(part_idx, desc_idx),
            'totalSize'    : self.get_video_size(part_idx, desc_idx),
            'hex'          : " ".join([f"{x:02x}" for x in self.get_desc(part_idx, desc_idx)])
        }
        return dic

    def load_partition_table(self):
        self.PART_OFFS = []
        self.SB_OFFS   = []

        self.disk.seek(self.PART_TABLE_OFF+0x34)
        partInfo = self.disk.read(64)

        self.num_parts = 0
        blkSize = 512
        # Stop at end of file, at an empty entry and after the maximum of 16
        # entries, so a missing or damaged terminator cannot loop forever.
        while (len(partInfo) == 64 and any(partInfo) and self.num_parts < 16 and
               partInfo[:4] != b"\xAA\x55\xAA\x55"):
            self.SB_OFFS.append(int.from_bytes(partInfo[20:24],
                                                byteorder='little') * blkSize)
            self.PART_OFFS.append(int.from_bytes(partInfo[48:56],
                                                byteorder='little') * blkSize)
            partInfo = self.disk.read(64)
            self.num_parts += 1

    def get_num_partitions(self):
        return self.num_parts

    def load_image(self, path):
        if self.img_loaded:
            self.disk.close()
            self.img_loaded = False

        self.disk = open(path, "rb")
        if self.disk.read(7) in [b'DHFS4.1']:
            self.load_partition_table()

            #TODO: It needs processing each partition
            self.disk.seek(self.PART_OFFS[0] + self.SB_OFFS[0] + 0x10)
            self.first_date = int.from_bytes(self.disk.read(4), byteorder='little')
            self.last_date = int.from_bytes(self.disk.read(4), byteorder='little')

            self.disk.seek(self.PART_OFFS[0] + self.SB_OFFS[0] + 0x2c)
            self.BLK_SIZE = int.from_bytes(self.disk.read(4), byteorder='little')
            self.FRAG_SIZE = int.from_bytes(self.disk.read(4),byteorder='little') * self.BLK_SIZE

            self.disk.seek(self.PART_OFFS[0] + self.SB_OFFS[0] + 0x38)
            self.FRAG_RESERVED = (int.from_bytes(self.disk.read(4), byteorder='little'))

            self.disk.seek(self.PART_OFFS[0] + self.SB_OFFS[0] + 0xF8)
            self.logs_offset = int.from_bytes(self.disk.read(4), byteorder='little') * self.BLK_SIZE

            self.img_loaded = True
            self.load_descs()
            self.print_metadata()
            #print ("Last offset: ", self.PART_OFFS[0] + self.VID_OFF + self.NUM_FRAGS*self.FRAG_SIZE )

        return self.img_loaded

    def get_image_metadata(self):
        if self.img_loaded:
            message  =  "*"*20+" Disk Metadata "+"*"*20+"\n"
            message += f"Block size: {self.BLK_SIZE}\n"
            message += f"Fragment Size: {self.FRAG_SIZE}\n"
            message += f"Fragments Reserved: {self.FRAG_RESERVED}/partition\n"
            for part_idx in range(self.num_parts):
                part_offset = self.PART_OFFS[part_idx]
                message += "-"*20+f" Partition {part_idx} "+"-"*20+"\n"
                message += f"\tDescriptors offset: {part_offset + self.DESC_OFF[part_idx]}\n"
                message += f"\tNumber of fragmentes: {self.NUM_FRAGS[part_idx]}\n"
                message += f"\tVideos offset: {part_offset + self.VID_OFF[part_idx]}\n"
                message += "\tVideos offset after reserved: "
                message += f"{part_offset + self.VID_OFF[part_idx] + self.FRAG_RESERVED*self.FRAG_SIZE}\n"
            return message
        else:
            return "No image loaded!!!"

    def print_metadata(self):
        print (self.get_image_metadata())

    def get_desc_types(self, part_idx):
        all_desc_types = {}
        for indx in range(self.NUM_FRAGS[part_idx]):
            desc_type = self.get_desc_type(part_idx, indx)
            all_desc_types[desc_type] = all_desc_types.get(desc_type, 0) + 1
        return all_desc_types

    def get_last_frag_size(self, part_idx, desc_idx):
        if self.get_desc_type(part_idx, desc_idx) == 1:
            desc = self.get_desc(part_idx, desc_idx)
            return int.from_bytes(desc[16:20], byteorder='little') * self.BLK_SIZE
        else:
            return self.get_last_frag_size(part_idx,
                            self.get_begin_desc(part_idx, desc_idx))

    def get_frags_video(self, part_idx, desc_idx):
        allFrags = []
        begDesc = desc_idx
        numFrags = self.get_num_frags(part_idx, desc_idx)

        idx = 0
        visited = set()
        # Descriptor 0 is a valid start (the first video of a partition); 0 only
        # ends the chain as a 'next' value. A corrupted chain may point back to
        # an earlier descriptor or past the table; stop there instead of
        # looping forever.
        first = True
        while ((first or (desc_idx != 0 and desc_idx != 0xFFFFFFFF)) and
               desc_idx < self.NUM_FRAGS[part_idx] and desc_idx not in visited):
            first = False
            visited.add(desc_idx)
            allFrags.append(desc_idx)
            idx += 1
            desc_idx = self.get_next_desc(part_idx, desc_idx)

        if  self.DEBUG and (idx > numFrags):
            print (f"\t\tVideo {begDesc} in partition {part_idx} has more frags "+
                   "than in main desc. 'Extract' will use greater size!")
        return allFrags

    def get_main_descs(self, part_idx):
        if self.img_loaded:
            for desc_idx in range(self.NUM_FRAGS[part_idx]):
                desc_type  = self.get_desc_type(part_idx, desc_idx)
                begin_time, end_time = self.get_timestamps(part_idx, desc_idx)

                if (desc_type in [1]) and begin_time != end_time:
                    yield desc_idx
        return

    def get_free_descs(self, part_idx):
        if self.img_loaded:
            for desc_idx in range(self.NUM_FRAGS[part_idx]):
                desc_type  = self.get_desc_type(part_idx, desc_idx)
                if desc_type == 0:
                    yield desc_idx
        return

    def get_dirty_descs(self, part_idx):
        if self.img_loaded:
            for desc_idx in range(self.NUM_FRAGS[part_idx]):
                desc_type  = self.get_desc_type(part_idx, desc_idx)

                if desc_type == 2:
                    begin_desc = self.get_begin_desc(part_idx, desc_idx)
                    frags_begin = self.frags_in_videos[part_idx].get(begin_desc, [])
                    if desc_idx not in frags_begin:
                        yield desc_idx
        return

    def load_descs(self):
        self.DESC_OFF = []
        self.VID_OFF = []
        self.NUM_FRAGS = []
        self.all_descs = []
        self.num_videos = []

        for part_offset in self.PART_OFFS:
            self.disk.seek(part_offset + self.SB_OFFS[0] + 0x44)
            self.DESC_OFF.append(int.from_bytes(self.disk.read(4),
                                        byteorder='little') * self.BLK_SIZE)
            self.VID_OFF.append(int.from_bytes(self.disk.read(4),
                                        byteorder='little') * self.BLK_SIZE)
            self.NUM_FRAGS.append(int.from_bytes(self.disk.read(4),
                                        byteorder='little'))

            self.disk.seek(part_offset + self.DESC_OFF[-1])
            self.all_descs.append(self.disk.read(self.DESC_SIZE * self.NUM_FRAGS[-1]))

        self.frags_in_videos = []
        self.free_frags = []
        self.dirty_frags = []

        for part_idx in range(self.num_parts):
            if self.DEBUG:
                print ("Partition: ", part_idx)
                print ("\tGetting desc types...")

            all_desc_types = self.get_desc_types(part_idx)

            if self.DEBUG:
                print ("\tLinking fragments to each main desc...")
            frags_in_videos = {}
            for desc_idx in self.get_main_descs(part_idx):
                frags_in_videos[desc_idx] = self.get_frags_video(part_idx, desc_idx)
            self.frags_in_videos.append(frags_in_videos)

            if self.DEBUG:
                print ("\tGetting free fragments...")
            self.free_frags.append([])
            for desc_idx in self.get_free_descs(part_idx):
                self.free_frags[part_idx].append(desc_idx)

            if self.DEBUG:
                print ("\tGetting dirty fragments...")
            self.dirty_frags.append([])
            for desc_idx in self.get_dirty_descs(part_idx):
                self.dirty_frags[part_idx].append(desc_idx)
                
        #print ("Fragmentos encadeados em videos", fragsInVideos)
        #print ("Fragmentos alocdos", fragsAloc)

    def get_slack_size(self, part_idx, desc_idx):
        if self.get_desc_type(part_idx, desc_idx) == 1:
            desc = self.get_desc(part_idx, desc_idx)
            return self.FRAG_SIZE - self.get_last_frag_size(part_idx, desc_idx)
        else:
            return self.get_slack_size(part_idx,
                            self.get_begin_desc(part_idx, desc_idx))

    def get_video_size(self, part_idx, desc_idx):
        return ((self.get_num_frags(part_idx, desc_idx) - 1) * self.FRAG_SIZE +
                self.get_last_frag_size(part_idx, desc_idx))

    def read_fragment(self, part_idx, fIndx):
        self.disk.seek(self.PART_OFFS[part_idx] + self.VID_OFF[part_idx] +
                        fIndx * self.FRAG_SIZE)
        return self.disk.read(self.FRAG_SIZE)

    def read_last_fragment(self, part_idx, fIndx):
        self.disk.seek(self.PART_OFFS[part_idx] + self.VID_OFF[part_idx] +
                        fIndx * self.FRAG_SIZE)
        return self.disk.read(self.get_last_frag_size(part_idx, fIndx))

    def read_slack_fragment (self, part_idx, fIndx):
        posSlack = self.get_last_frag_size(part_idx, fIndx)
        self.disk.seek(self.PART_OFFS[part_idx] + self.VID_OFF[part_idx] +
                        fIndx * self.FRAG_SIZE + posSlack)
        return self.disk.read(self.FRAG_SIZE - posSlack)

    def save_video_at (self, part_idx, desc_idx, path, logFunc = None):
        if self.img_loaded:
            date     = self.get_begin_date(part_idx, desc_idx)
            begin    = self.get_begin_time(part_idx, desc_idx)
            end      = self.get_end_time(part_idx, desc_idx)
            cam      = self.get_camera(part_idx, desc_idx)
            totFrag  = self.get_num_frags(part_idx, desc_idx)

            file_name  = f"Video-p{part_idx}-{desc_idx:06d}-{date.replace('-','')}-"
            file_name += f"{begin.replace(':','')}-{end.replace(':','')}-"
            file_name += f"ch{cam:02d}.h264"
            fullName   = path+"/"+file_name

            with open (fullName, "wb") as fd_out:
                frags = self.frags_in_videos[part_idx][desc_idx]
                frag_idx = 0
                for frag_idx in range(len(frags) - 1):
                    fd_out.write(self.read_fragment(part_idx, frags[frag_idx]))
                    frag_idx += 1
                    if logFunc:
                        logFunc(f"Saving {file_name} ({frag_idx*100/len(frags):4.2f}%)")
                fd_out.write(self.read_last_fragment(part_idx, frags[frag_idx]))
                fd_out.close()
            return file_name
        else:
            return None

    def save_slack_at (self, idx, part_idx, desc_idx, path, log_func = None):
        if self.img_loaded and self.get_slack_size(part_idx, desc_idx) > 0:
            date     = self.get_begin_date(part_idx, desc_idx)
            begin    = self.get_begin_time(part_idx, desc_idx)
            end      = self.get_end_time(part_idx, desc_idx)
            cam      = self.get_camera(part_idx, desc_idx)
            file_name = f"{idx:04d}-Slack-p{part_idx}-{desc_idx:06d}-"
            file_name += f"{date.replace('-','')}-"
            file_name += f"{begin.replace(':','')}-{end.replace(':','')}-"
            file_name += f"ch{cam:02d}.h264"
            full_name = path+"/"+file_name

            with open (full_name, "wb") as fd_out:
                if log_func: log_func(f"Saving {file_name}")

                last_desc = self.frags_in_videos[part_idx][desc_idx][-1]
                fd_out.write(self.read_slack_fragment(part_idx, last_desc))
                fd_out.close()
            return file_name
        else:
            return None

    def save_recovered_at_free (self, part_idx, path, log_func):
        tot_videos = 0
        file_desc = None
        signature = self.config['CARVE_SIGNAT']

        for frag_idx in self.free_frags[part_idx]:
            frag_data = self.read_fragment(part_idx, frag_idx)

            #Looks for signature in first 32 bytes
            if signature.search(frag_data[:32]):
                if file_desc:
                    tot_videos += 1
                    file_desc.close()

                fileName = f"FragFree-{frag_idx:06d}.h264"
                file_desc = open(path+"/"+fileName, "wb")
                file_desc.write(frag_data)
                if log_func:
                    log_func(f"Saving vídeo {fileName}")
            elif file_desc:
                file_desc.write(frag_data)

        if file_desc:
            tot_videos += 1
            file_desc.close()

        return tot_videos

    def save_recovered_at_dirty (self, part_idx, path, log_func):
        tot_videos = 0
        num_descs = self.NUM_FRAGS[part_idx]
        # A set keeps membership checks fast on disks with millions of
        # descriptors; iterating the list directly avoids running past its end
        # when a chain also contains descriptors that are not in the list.
        already_saved = set()

        for desc_idx in self.dirty_frags[part_idx]:
            if desc_idx in already_saved:
                continue

            date     = self.get_begin_date(part_idx, desc_idx)
            begin    = self.get_begin_time(part_idx, desc_idx)
            cam      = self.get_camera(part_idx, desc_idx)
            file_name = f"FragDirty-p{part_idx}-{desc_idx:06d}-{date.replace('-','')}-"
            file_name += f"{begin.replace(':','')}-"
            file_name += f"ch{cam:02d}.h264"
            full_name = path+"/"+file_name

            file_desc = open(full_name, "wb")
            if log_func:
                log_func(f"Saving vídeo {file_name}")

            file_desc.write(self.read_fragment(part_idx, desc_idx))
            already_saved.add(desc_idx)
            nextDesc = self.get_next_desc(part_idx, desc_idx)
            if self.DEBUG:
                print (f"part_idx {part_idx} desc_idx {desc_idx} nextDesc {nextDesc}"+
                       f"baseDesc {self.get_begin_desc(part_idx, desc_idx)} ")

            while (nextDesc != 0 and nextDesc < num_descs and
                   nextDesc not in already_saved and
                   self.get_begin_desc(part_idx, desc_idx) ==
                   self.get_begin_desc(part_idx, nextDesc)):
                desc_idx = nextDesc
                file_desc.write(self.read_fragment(part_idx, desc_idx))
                already_saved.add(desc_idx)
                nextDesc = self.get_next_desc(part_idx, desc_idx)

                if self.DEBUG:
                    print (f"part_idx {part_idx} desc_idx {desc_idx} nextDesc {nextDesc}"+
                           f"baseDesc {self.get_begin_desc(part_idx, desc_idx)} ")

            file_desc.close()
            tot_videos += 1
        return tot_videos

    def save_recovered_videos(self, part_idx, path, log_func = None):
        tot_videos = 0
        if self.img_loaded:
            tot_videos  = self.save_recovered_at_free (part_idx, path, log_func)
            tot_videos += self.save_recovered_at_dirty(part_idx, path, log_func)
        return tot_videos


    def save_logs(self, fullPath):
        self.disk.seek(self.logs_offset)
        logs_header = self.disk.read(2 * self.BLK_SIZE)
        logs_size = int.from_bytes(logs_header[:4], byteorder='little') - 2 * self.BLK_SIZE

        file_desc = open(fullPath, "wb")
        file_desc.write(self.disk.read(logs_size))
        file_desc.close()

    def set_config(self, fileName):
        castings = {"CARVE_SIGNAT" : lambda e: re.compile(("^"+e).encode()),
                    "DEBUG" : bool}

        file_desc = open (fileName, "r")
        for line in file_desc:
            line = line.strip()
            if (len(line) > 0) and (line[0] != "#"):
                eq_pos = line.find("=")
                if eq_pos > 0:
                    key   = line[:eq_pos].strip()
                    value = line[eq_pos+1:].strip()
                    self.config[key] = castings[key](value)
        file_desc.close()
        self.DEBUG = self.config['DEBUG']