from linuxautomaton import sp, sv, common


class StatedumpStateProvider(sp.StateProvider):
    def __init__(self, state):
        self.state = state
        self.tids = state.tids
        self.disks = state.disks
        cbs = {
            'lttng_statedump_process_state':
            self._process_lttng_statedump_process_state,
            'lttng_statedump_file_descriptor':
            self._process_lttng_statedump_file_descriptor,
            'lttng_statedump_block_device':
            self._process_lttng_statedump_block_device,
        }
        self._register_cbs(cbs)

    def process_event(self, ev):
        self._process_event_cb(ev)

    def merge_fd_dict(self, p, parent):
        if len(p.fds.keys()) != 0:
            toremove = []
            for fd in p.fds.keys():
                if fd not in parent.fds.keys():
                    parent.fds[fd] = p.fds[fd]
                else:
                    # best effort to fix the filename
                    if len(parent.fds[fd].filename) == 0:
                        parent.fds[fd].filename = p.fds[fd].filename
                    # merge the values as they are for the same sv.FD
                    parent.fds[fd].net_read += p.fds[fd].net_read
                    parent.fds[fd].net_write += p.fds[fd].net_write
                    parent.fds[fd].disk_read += p.fds[fd].disk_read
                    parent.fds[fd].disk_write += p.fds[fd].disk_write
                    parent.fds[fd].open += p.fds[fd].open
                    parent.fds[fd].close += p.fds[fd].close
                toremove.append(fd)
            for fd in toremove:
                p.fds.pop(fd, None)
        if len(p.closed_fds.keys()) != 0:
            for fd in p.closed_fds.keys():
                if fd not in parent.closed_fds.keys():
                    parent.closed_fds[fd] = p.closed_fds[fd]
                else:
                    # best effort to fix the filename
                    if len(parent.closed_fds[fd].name) == 0:
                        parent.closed_fds[fd].name = p.closed_fds[fd].name
                    # merge the values as they are for the same sv.FD
                    parent.closed_fds[fd].read += p.closed_fds[fd].read
                    parent.closed_fds[fd].write += p.closed_fds[fd].write
                    parent.closed_fds[fd].open += p.closed_fds[fd].open
                    parent.closed_fds[fd].close += p.closed_fds[fd].close
                p.closed_fds.pop(fd, None)

    def _process_lttng_statedump_process_state(self, event):
        tid = event["tid"]
        pid = event["pid"]
        name = event["name"]
        if tid not in self.tids:
            p = sv.Process()
            p.tid = tid
            self.tids[tid] = p
        else:
            p = self.tids[tid]
        # Even if the process got created earlier, some info might be
        # missing, add it now.
        p.pid = pid
        p.comm = name

        if pid != tid:
            # create the parent
            if pid not in self.tids:
                parent = sv.Process()
                parent.tid = pid
                parent.pid = pid
                parent.comm = name
                self.tids[pid] = parent
            else:
                parent = self.tids[pid]
            # If the thread had opened sv.FDs, they need to be assigned
            # to the parent.
            self.merge_fd_dict(p, parent)

    def _process_lttng_statedump_file_descriptor(self, event):
        pid = event["pid"]
        fd = event["fd"]
        filename = event["filename"]

        if pid not in self.tids:
            p = sv.Process()
            p.pid = pid
            p.tid = pid
            self.tids[pid] = p
        else:
            p = self.tids[pid]

        if fd not in p.fds.keys():
            newfile = sv.FD()
            newfile.filename = filename
            newfile.fd = fd
            # FIXME: we don't have the info, just assume for now
            newfile.cloexec = 1
            p.fds[fd] = newfile
        else:
            # just fix the filename
            p.fds[fd].filename = filename

    def _process_lttng_statedump_block_device(self, event):
        d = common.get_disk(event["dev"], self.disks)
        d.prettyname = event["diskname"]
