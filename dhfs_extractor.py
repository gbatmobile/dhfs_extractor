# encoding: utf-8

version = "DHFS4.1 Extractor 0.5"
copyright = \
'''
This program can identify and recover videos stored\n\
in a DHFS4.1 filesystem (common in chinese's DVR). \n\n\
When running under Windows, use 'Open Image' to get data\n\
source. In Linux you can access evidence disks or images\n\
using their names in file system. \n\n\
DHFS4.1 extractor is offered to you under MIT license\n\
by GALILEU Batista (galileu.batista@ifrn.edu.br)\n\
You must retain author name in all circunstances in which\n\
the program is used. He has made the best to get \n\
a correct operation, but no warranty implicit or explicit\n\
is provided.
'''

from dhfs41 import *
import wx
import os
import time

class DVRExtractor (wx.Frame):
    def __init__(self, *args, **kwargs):
        super(DVRExtractor, self).__init__(*args, **kwargs)
        self.SetSize(840,530)
        self.dhfs = DHFS41(DEBUG=DEBUG)
        self.create_gui()

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def create_gui(self):
        self.CreateStatusBar()

        splitter = wx.SplitterWindow(self, style=wx.SP_NOSASH)
        self.painel = wx.Panel(splitter)
        self.painel1 = wx.Panel(splitter)
        splitter.SplitVertically(self.painel1, self.painel)
        splitter.SetSashGravity(0.27)

        # ToolBar
        self.ToolBar = wx.ToolBar(self, wx.ID_ANY, style=wx.TB_TEXT)
        self.ToolBar.AddTool(toolId=101, label="Open Image",
                bitmap=wx.Bitmap(self.resource_path("icons/abrir.png")))
        if os.name != 'nt':
            self.ToolBar.AddTool(toolId=102, label="Open Disk",
                bitmap=wx.Bitmap(self.resource_path("icons/abrir.png")))
        self.ToolBar.AddTool(toolId=103, label="Info",
                bitmap=wx.Bitmap(self.resource_path("icons/info.png")))
        self.ToolBar.AddTool(toolId=104, label="Extract",
                bitmap=wx.Bitmap(self.resource_path("icons/extract.png")))
        self.ToolBar.AddTool(toolId=112, label="Extract by Date",
                bitmap=wx.Bitmap(self.resource_path("icons/extract.png")))
        self.ToolBar.AddTool(toolId=105, label="MetaData",
                bitmap=wx.Bitmap(self.resource_path("icons/metadata.png")))
        self.ToolBar.AddTool(toolId=106, label="Slack",
                bitmap=wx.Bitmap(self.resource_path("icons/slack.png")))
        self.ToolBar.AddTool(toolId=107, label="Recover",
                bitmap=wx.Bitmap(self.resource_path("icons/recover.png")))
        self.ToolBar.AddTool(toolId=108, label="Logs",
                bitmap=wx.Bitmap(self.resource_path("icons/logs.png")))
        self.ToolBar.AddTool(toolId=109, label="Config",
                bitmap=wx.Bitmap(self.resource_path("icons/config.png")))
        self.ToolBar.AddTool(toolId=110, label="About",
                bitmap=wx.Bitmap(self.resource_path("icons/info.png")))
        self.ToolBar.AddTool(toolId=111, label="Exit",
                bitmap=wx.Bitmap(self.resource_path("icons/exit.png")))
        self.ToolBar.Bind(wx.EVT_TOOL, self.toolBarEvent)
        self.ToolBar.Realize()

        self.SetTitle(version)
        self.Centre()

        self.lb_videos = wx.ListCtrl(self.painel, -1, pos=(0, 0),
                                    size=(585, 400),
                                    style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.lb_videos_headers = ["PART", "ID", "DATA", "BEGIN", "END", "CAMERA", "SIZE"]
        self.lb_videos.SetBackgroundColour(wx.WHITE)
        for i in range(len(self.lb_videos_headers)):
            self.lb_videos.InsertColumn(i+1, self.lb_videos_headers[i],
                                            wx.LIST_FORMAT_CENTER,
                                            width=wx.LIST_AUTOSIZE)

        wx.StaticText(self.painel1, label="Date", pos=(40, 10))
        wx.StaticText(self.painel1, label="Camera", pos=(125, 10))

        # ListBoxes para selecionar datas e câmeras
        self.lb_dates = wx.ListBox(self.painel1, pos=(10, 30), size=(100, 370),
                                    style=wx.LB_SINGLE)
        self.Bind(wx.EVT_LISTBOX, self.filter_videos, self.lb_dates)

        self.lb_cameras = wx.ListBox(self.painel1, pos=(120, 30), size=(70, 370),
                                    style=wx.LB_SINGLE)
        self.Bind(wx.EVT_LISTBOX, self.filter_videos, self.lb_cameras)

        self.Show(True)
        time.sleep(1)
        self.show_about()


    def toolBarEvent(self, e):
        if e.GetId() == 101:
            self.load_image()
        elif e.GetId() == 102:
            self.load_disk()
        elif e.GetId() == 103:
            self.show_metadata()
        elif e.GetId() == 104:
            self.save_videos()
        elif e.GetId() == 112:
            self.save_videos_by_date()
        elif e.GetId() == 105:
            self.export_videos_metadata()
        elif e.GetId() == 106:
            self.save_slacks()
        elif e.GetId() == 107:
            self.save_recovered()
        elif e.GetId() == 108:
            self.save_logs()
        elif e.GetId() == 109:
            self.config()
        elif e.GetId() == 110:
            self.show_about()
        elif e.GetId() == 111:
            self.close()

    def clear_gui(self):
        self.lb_dates.Clear()
        self.lb_cameras.Clear()
        self.lb_videos.DeleteAllItems()
        self.SetStatusText("")

    def load_disk(self):
        self.load_image()

    def load_image(self):
        self.clear_gui()

        self.dlg = wx.FileDialog(self, "Escolha um arquivo", os.getcwd(), "")
        if self.dlg.ShowModal() == wx.ID_OK:
            fileName = self.dlg.GetPath()

            self.SetStatusText("Loading Image...")
            if self.dhfs.load_image(fileName):
                self.show_videos_info()
            else:
                self.SetStatusText("")
                wx.MessageBox("This is not a DHFS4.1 filesystem!!!", version,
                                style=wx.OK | wx.ICON_INFORMATION)

    def show_about(self):
        wx.MessageBox(copyright, "About", style=wx.OK)

    def show_metadata(self):
        message = self.dhfs.get_image_metadata()
        if message:
            wx.MessageBox(message, "DHFS4.1 Metadata", style=wx.OK)
        else:
            wx.MessageBox("No image/disk loaded!!!!!!", "Warning", style=wx.OK)

    def show_videos_info(self):
        all_video_dates  = []
        all_cameras      = []
        for p_idx in range(self.dhfs.get_num_partitions()):
            for d_idx in self.dhfs.get_main_descs(p_idx):
                video_date = self.dhfs.get_begin_date(p_idx, d_idx)
                if not video_date in all_video_dates:
                    all_video_dates.append(video_date)

                camera = f"{self.dhfs.get_camera(p_idx, d_idx):02d}"
                if not camera in all_cameras:
                    all_cameras.append(camera)

        all_video_dates.sort()
        all_video_dates.insert(0, "All")
        all_cameras.sort()
        all_cameras.insert(0, "All")

        self.lb_dates.InsertItems(all_video_dates, 0)
        self.lb_dates.SetSelection(0)

        self.lb_cameras.InsertItems(all_cameras, 0)
        self.lb_cameras.SetSelection(0)

        self.filter_videos(None)

    def filter_videos(self, evt):
        self.lb_videos.DeleteAllItems()

        vid_scanned = 0
        video_idx = 0
        tot_videos = sum(len(videos) for videos in self.dhfs.frags_in_videos)
        for part_idx in range(self.dhfs.get_num_partitions()):
            for desc_idx in self.dhfs.get_main_descs(part_idx):
                date  = self.dhfs.get_begin_date(part_idx, desc_idx)
                begin = self.dhfs.get_begin_time(part_idx, desc_idx)
                end   = self.dhfs.get_end_time(part_idx, desc_idx)
                cam   = f"{self.dhfs.get_camera(part_idx, desc_idx):02d}"
                size  = f"{self.dhfs.get_video_size(part_idx, desc_idx)/1024**2:.2f} MB"

                selectedDate = self.lb_dates.GetStringSelection()
                selectedCam = self.lb_cameras.GetStringSelection()

                if (((selectedDate == "All") or (selectedDate == date)) and
                    ((selectedCam == "All") or (selectedCam == cam))):
                    self.lb_videos.InsertItem(video_idx, str(part_idx))
                    self.lb_videos.SetItem(video_idx, 1, str(desc_idx))
                    self.lb_videos.SetItem(video_idx, 2, date)
                    self.lb_videos.SetItem(video_idx, 3, begin)
                    self.lb_videos.SetItem(video_idx, 4, end)
                    self.lb_videos.SetItem(video_idx, 5, cam)
                    self.lb_videos.SetItem(video_idx, 6, size)
                    video_idx += 1

                vid_scanned += 1
                if vid_scanned % 50 == 0:
                    self.SetStatusText("Listing Videos... {0:.2f}%".format((vid_scanned/tot_videos) * 100))

        self.SetStatusText("Done!!!!!!!!!")

    def get_save_path(self):
        self.dlg = wx.DirDialog(self, "Choose a dir to save...", os.getcwd(),
                        wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        return self.dlg.GetPath() if self.dlg.ShowModal() == wx.ID_OK else None

    def save_videos(self):
        if not self.dhfs.img_loaded:
            wx.MessageBox("No image/disk loaded!!!!!!", "Warning", style=wx.OK)
            return

        dir_save = self.get_save_path()
        if dir_save:
            tot_videos = 0
            for lb_video_idx in range(self.lb_videos.GetItemCount()):
                if self.lb_videos.IsSelected(lb_video_idx):
                    part_idx = int(self.lb_videos.GetItemText(lb_video_idx, 0))
                    vid_idx = int(self.lb_videos.GetItemText(lb_video_idx, 1))
                    self.dhfs.save_video_at(part_idx, vid_idx, dir_save, self.SetStatusText)
                    tot_videos += 1
            self.SetStatusText(f"Done!!!")

            if tot_videos == 0:
                wx.MessageBox("Choose one or more videos!!!", version,
                                    style=wx.OK | wx.ICON_INFORMATION)

    def save_videos_by_date(self):
        if not self.dhfs.img_loaded:
            wx.MessageBox("No image/disk loaded!!!!!!", "Warning", style=wx.OK)
            return

        selectedDate = self.lb_dates.GetStringSelection()
        if not selectedDate or selectedDate == "All":
            wx.MessageBox("Please select a specific date from the Date list!", version,
                            style=wx.OK | wx.ICON_INFORMATION)
            return

        selectedCam = self.lb_cameras.GetStringSelection()

        # Count how many videos match the current filter
        video_count = 0
        for part_idx in range(self.dhfs.get_num_partitions()):
            for desc_idx in self.dhfs.get_main_descs(part_idx):
                date = self.dhfs.get_begin_date(part_idx, desc_idx)
                cam = f"{self.dhfs.get_camera(part_idx, desc_idx):02d}"
                
                if (date == selectedDate and
                    ((selectedCam == "All") or (selectedCam == cam))):
                    video_count += 1

        if video_count == 0:
            wx.MessageBox("No videos found for the selected date/camera!", version,
                            style=wx.OK | wx.ICON_INFORMATION)
            return

        # Confirm with user
        camera_info = f" from camera {selectedCam}" if selectedCam != "All" else " from all cameras"
        message = f"Extract {video_count} video(s) from {selectedDate}{camera_info}?"
        dlg = wx.MessageDialog(self, message, "Confirm Extraction", 
                               wx.YES_NO | wx.ICON_QUESTION)
        
        if dlg.ShowModal() != wx.ID_YES:
            return

        dir_save = self.get_save_path()
        if dir_save:
            tot_videos = 0
            for part_idx in range(self.dhfs.get_num_partitions()):
                for desc_idx in self.dhfs.get_main_descs(part_idx):
                    date = self.dhfs.get_begin_date(part_idx, desc_idx)
                    cam = f"{self.dhfs.get_camera(part_idx, desc_idx):02d}"
                    
                    if (date == selectedDate and
                        ((selectedCam == "All") or (selectedCam == cam))):
                        self.dhfs.save_video_at(part_idx, desc_idx, dir_save, self.SetStatusText)
                        tot_videos += 1
            
            self.SetStatusText(f"Done! Extracted {tot_videos} video(s)")
            wx.MessageBox(f"{tot_videos} video(s) successfully extracted from {selectedDate}!", 
                         version, style=wx.OK | wx.ICON_INFORMATION)

    def export_videos_metadata(self):
        if not self.dhfs.img_loaded:
            wx.MessageBox("No image/disk loaded!!!!!!", "Warning", style=wx.OK)
            return

        file_dialog = wx.FileDialog(self, "Save Videos Metadata file",
                        wildcard="csv (*.csv)|*.csv",
                        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if file_dialog.ShowModal() == wx.ID_CANCEL: return

        fd_out = open (file_dialog.GetPath(), "w")
        fd_out.write(";".join(self.lb_videos_headers)+"\n")
        tot_videos = 0
        for lb_video_idx in range(self.lb_videos.GetItemCount()):
            if self.lb_videos.IsSelected(lb_video_idx):
                metadata = ";".join([self.lb_videos.GetItemText(lb_video_idx, i)
                                        for i in range(7)])
                fd_out.write(metadata+"\n")
                tot_videos += 1
        fd_out.close()

        if tot_videos == 0:
            wx.MessageBox("Choose one or more videos!!!", version,
                            style=wx.OK | wx.ICON_INFORMATION)

    def save_slacks(self):
        if not self.dhfs.img_loaded:
            wx.MessageBox("No image/disk loaded!!!!!!", "Warning", style=wx.OK)
            return

        dir_save = self.get_save_path()
        if dir_save:
            tot_slack = 0
            for lb_video_idx in range(self.lb_videos.GetItemCount()):
                if self.lb_videos.IsSelected(lb_video_idx):
                    part_idx = int(self.lb_videos.GetItemText(lb_video_idx, 0))
                    video_idx = int(self.lb_videos.GetItemText(lb_video_idx, 1))
                    self.dhfs.save_slack_at(tot_slack, part_idx, video_idx, dir_save, self.SetStatusText)
                    tot_slack += 1
            self.SetStatusText(f"Done!!!")

            if tot_slack == 0:
                wx.MessageBox("Choose one or more slacks!!!", version,
                                    style=wx.OK | wx.ICON_INFORMATION)

    def save_recovered(self):
        if not self.dhfs.img_loaded:
            wx.MessageBox("No image/disk loaded!!!!!!", "Warning", style=wx.OK)
            return

        dir_save = self.get_save_path()
        if dir_save:
            tot_videos = 0
            for part_idx in range(self.dhfs.get_num_partitions()):
                tot_videos += self.dhfs.save_recovered_videos(part_idx, dir_save, self.SetStatusText)
            self.SetStatusText(f"Done!!!")
            wx.MessageBox(f"{tot_videos} Video(s) sucessfully saved.", style=wx.OK)

    def save_logs(self):
        if not self.dhfs.img_loaded:
            wx.MessageBox("No image/disk loaded!!!!!!", "Warning", style=wx.OK)
            return

        file_dialog = wx.FileDialog(self, "Save Log file",
                        wildcard="log (*.log)|*.log",
                        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)

        if file_dialog.ShowModal() == wx.ID_CANCEL: return

        file_save = file_dialog.GetPath()
        self.dhfs.save_logs (file_save)

    def config(self):
        wx.MessageBox("You will be inquired to open one config file.\n\n"+
                      "This file should have the format:\n"+
                      "key1 = VALUE1\n"+
                      "key2 = VALUE2\n"+
                      "key3 = VALUE3\n\n"+
                      "At the moment only two keys are supported:\n"+
                      "CARVE_SIGNAT=regex python to use in video carving\n"+
                      "DEBUG=True or False",
                      "Info", style=wx.OK)

        self.dlg = wx.FileDialog(self, "Escolha um arquivo", os.getcwd(), "")
        if self.dlg.ShowModal() == wx.ID_OK:
            file_name = self.dlg.GetPath()
            try:
                self.dhfs.set_config(file_name)
            except Exception as e:
                wx.MessageBox("Error in processing config file:\n"+str(e),
                            "Info", style=wx.OK)

DEBUG = True
if __name__ == '__main__':
    app = wx.App()
    main = DVRExtractor(None)
    app.MainLoop()
