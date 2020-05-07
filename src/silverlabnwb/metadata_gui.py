
import collections
import tkinter as T
from tkinter import messagebox, ttk
from idlelib.tooltip import Hovertip
from ruamel.yaml import YAML

from . import metadata


def wrap_dict(metadata):
    """Convert a metadata dict to use Tk variables to wrap entries."""
    return {key: wrap_value(value) for key, value in metadata.items()}


def wrap_list(metadata):
    """Convert a list of metadata components to use Tk variables."""
    return [wrap_value(item) for item in metadata]


def wrap_value(value):
    """Wrap a value as a Tk variable, or nested structure thereof.

    String values will automatically be stripped.
    """
    if isinstance(value, collections.Mapping):
        wrapped = wrap_dict(value)
    elif isinstance(value, list):
        wrapped = wrap_list(value)
    elif isinstance(value, str):
        wrapped = T.StringVar()
        wrapped.set(value.strip())
    elif isinstance(value, float):
        wrapped = T.DoubleVar()
        wrapped.set(value)
    elif isinstance(value, int):
        wrapped = T.IntVar()
        wrapped.set(value)
    elif isinstance(value, bool):
        wrapped = T.BooleanVar()
        wrapped.set(value)
    elif isinstance(value, T.Variable):
        # Clone the particular type of tkinter variable
        wrapped = type(value)()
        value = value.get()
        if hasattr(value, 'strip'):
            value = value.strip()
        wrapped.set(value)
    elif value is None:
        wrapped = T.StringVar()
        wrapped.set('')
    else:
        raise ValueError('Unexpected metadata item {} of type {}'.format(value, type(value)))
    return wrapped


def add_yaml_representers(yaml_instance):
    """Add YAML representers that convert Tk variables to their Python contents."""
    def get_repr(kind):
        def representer(dumper, data):
            data = data.get()
            rep = getattr(dumper, 'represent_' + kind)
            return rep(data)
        return representer
    yaml_instance.representer.add_representer(T.StringVar, get_repr('str'))
    yaml_instance.representer.add_representer(T.DoubleVar, get_repr('float'))
    yaml_instance.representer.add_representer(T.IntVar, get_repr('int'))
    yaml_instance.representer.add_representer(T.BooleanVar, get_repr('bool'))


def strip_empty_vars(metadata):
    """Return a copy of the metadata that has no empty StringVar instances."""
    if isinstance(metadata, collections.Mapping):
        result = {}
        for key, value in metadata.items():
            result[key] = strip_empty_vars(value)
            if result[key] is None:
                del result[key]
    elif isinstance(metadata, list):
        result = [stripped
                  for stripped in (strip_empty_vars(item) for item in metadata)
                  if stripped is not None]
    elif (hasattr(metadata, 'get') and isinstance(metadata.get(), str) and
          metadata.get().strip() == ''):
        result = None
    else:
        result = metadata
    return result


class MetadataEditor(ttk.Frame):
    """A simple Tkinter GUI to help researchers fill in experiment metadata."""
    def __init__(self, master=None):
        """Initialise the GUI."""
        ttk.Frame.__init__(self, master)
        # Load the merged metadata from file, and extract the template experiment
        user_metadata, self.comments = metadata.read_user_config()
        self.template_expt = user_metadata['experiments'].pop('template')
        self.template_expt_comments = self.comments['experiments'].pop('template')
        del user_metadata['devices']  # Until we support editing it
        self.metadata = wrap_dict(user_metadata)
        self.yaml_instance = YAML(typ='safe')
        add_yaml_representers(self.yaml_instance)
        # self.original_metadata = copy.deepcopy(self.metadata)
        # Action buttons
        # ttk.Button(self, text="REVERT", command=self.revert).grid(
        #     row=0, column=0, sticky=T.W, padx=5, pady=5)
        ttk.Button(self, text="SAVE", command=self.save).grid(
            row=0, column=1, sticky=T.W, padx=5, pady=5)
        ttk.Button(self, text="DONE", command=self.done).grid(
            row=0, column=2, sticky=T.W, padx=5, pady=5)
        # Content tabs
        tabs = self.tabs = ttk.Notebook(self, padding=2)
        self.session_tab = self.make_session_tab(tabs)
        self.people_tab = self.make_people_tab(tabs)
        self.expts_tab = self.make_expts_tab(tabs)
        tabs.enable_traversal()
        tabs.grid(row=1, column=0, columnspan=3)
        # Resize support - make the content section take it all
        self.rowconfigure(1, weight=1)
        self.columnconfigure('all', weight=1)
        tabs.rowconfigure('all', weight=1)
        tabs.columnconfigure('all', weight=1)
        self.pack(side="top", fill="both", expand=True)

    def save(self):
        """Save current settings to file.

        TODO: Give the user some indication that this has happened!
        """
        self.record_expt()  # The only part that doesn't sync by itself
        metadata.save_config_file(strip_empty_vars(self.metadata), self.yaml_instance)

    def done(self):
        """Save settings and quit the editor."""
        self.save()
        self.master.destroy()

    # def revert(self):
    #     """Revert all metadata changes made by this editor."""
    #     self.metadata = copy.deepcopy(self.original_metadata)
    #     self.save()

    def make_people_tab(self, parent):
        """Build the people tab and add it to the parent."""
        frame = ttk.Frame(parent)
        # Choosing who to edit
        ttk.Label(frame, text='Edit person:').grid(row=0, column=0, sticky='e')
        person_list = ttk.Combobox(frame, state='readonly', width=10,
                                   values=sorted(self.metadata['people'].keys()))
        person_list.bind('<<ComboboxSelected>>',
                         lambda e: self.update_people_tab(person_list.get()))
        person_list.grid(row=0, column=1, sticky='w')
        # Section for adding new people
        ttk.Label(frame, text='New person:').grid(
            row=2, column=0, sticky='e')
        new_person_var = T.StringVar()
        ttk.Entry(frame, textvariable=new_person_var, width=10).grid(
            row=2, column=1, sticky='w')
        # TODO: Make hitting return in the Entry click the Add button
        # TODO: Make the Add button stick next to the Entry box
        ttk.Button(frame, text='Add',
                   command=lambda: self.add_person(new_person_var.get(),
                                                   person_list)).grid(
            row=2, column=2, sticky='w')
        # Fields to edit current person
        widgets = self.session_widgets = {}
        ttk.Label(frame, text='Full name:').grid(row=0, column=4, sticky='e')
        widgets['name'] = ttk.Entry(frame)
        widgets['name'].grid(row=0, column=5, sticky='w')
        ttk.Label(frame, text='ORCID:').grid(row=1, column=4, sticky='e')
        widgets['orcid'] = ttk.Entry(frame)
        widgets['orcid'].grid(row=1, column=5, sticky='w')
        ttk.Label(frame, text='SCOPUS ID:').grid(row=2, column=4, sticky='e')
        widgets['scopus_id'] = ttk.Entry(frame)
        widgets['scopus_id'].grid(row=2, column=5, sticky='w')
        if self.metadata['people']:
            person_list.set(person_list['values'][0])
            self.update_people_tab(person_list.get())
        # Resize support
        frame.rowconfigure('all', weight=0)
        frame.columnconfigure(0, weight=2)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(6, weight=2)
        parent.add(frame, text='People')
        return frame

    def update_people_tab(self, person_id):
        """Associate the entry boxes with the given person's details."""
        assert person_id in self.metadata['people']
        person = self.metadata['people'][person_id]
        widgets = self.session_widgets
        for key in ['name', 'orcid', 'scopus_id']:
            if key not in person:
                # Optional item was not present before
                person[key] = T.StringVar()
            widgets[key]['textvariable'] = person[key]

    def add_person(self, person_id, person_list_box):
        """Add a new researcher."""
        # TODO: Update the 'edit person' dropdown to match person_id
        existing_people = person_list_box['values']
        if person_id in existing_people:
            messagebox.showerror(message='The person ID "{}" already exists'.format(person_id))
            return
        if not person_id.isalnum():
            messagebox.showerror(message='A person ID can only contain letters and numbers')
            return
        person_list_box['values'] = sorted(existing_people + (person_id,))
        self.session_researcher_box['values'] = person_list_box['values']
        name_var = T.StringVar()
        name_var.set(person_id)
        self.metadata['people'][person_id] = {'name': name_var}
        self.update_people_tab(person_id)

    def make_session_tab(self, parent):
        """Build a tab for setting session properties."""
        frame = ttk.Frame(parent)
        ttk.Label(frame, text='Description:').grid(row=2, column=0, sticky='e')
        desc = ttk.Entry(frame, width=70)
        desc.grid(row=2, column=1, sticky='w')

        ttk.Label(frame, text='Researcher:').grid(row=0, column=0, sticky='e')
        researcher = ttk.Combobox(frame, state='readonly',
                                  values=sorted(self.metadata['people'].keys()))
        researcher.bind('<<ComboboxSelected>>',
                        lambda e: self.update_session(person=researcher.get(),
                                                      expt=experiment,
                                                      desc=desc))
        researcher.grid(row=0, column=1, sticky='w')
        self.session_researcher_box = researcher

        ttk.Label(frame, text='Experiment:').grid(row=1, column=0, sticky='e')
        experiment = ttk.Combobox(frame, state='readonly',
                                  values=sorted(self.metadata['experiments'].keys()))
        experiment.bind('<<ComboboxSelected>>',
                        lambda e: self.update_session(person=researcher.get(),
                                                      expt=experiment.get()))
        experiment.grid(row=1, column=1, sticky='w')
        self.session_experiment_box = experiment

        if 'last_session' not in self.metadata:
            self.metadata['last_session'] = T.StringVar()
            self.metadata['last_session'].set(researcher['values'][0])
        last_person = self.metadata['last_session'].get()
        researcher.set(last_person)
        self.update_session(person=researcher.get(), desc=desc, expt=experiment)
        # Resize support & add to tabs
        frame.rowconfigure('all', weight=0)
        frame.columnconfigure('all', weight=1)
        parent.add(frame, text='This session')
        return frame

    def update_session(self, person, desc=None, expt=None):
        """Update session info to reflect changes in the dropdowns."""
        self.metadata['last_session'].set(person)
        if person not in self.metadata['sessions']:
            self.metadata['sessions'][person] = {
                'description': T.StringVar(),
                'experiment': T.StringVar()
            }
            self.metadata['sessions'][person]['description'].set(
                "One or two sentences describing the experiment and data in the file.")
        if desc is not None:
            desc['textvariable'] = self.metadata['sessions'][person]['description']
        if expt is not None:
            expt_var = self.metadata['sessions'][person]['experiment']
            if isinstance(expt, str):
                expt_var.set(expt)
            else:
                expt.set(expt_var.get())

    def make_expts_tab(self, parent):
        """Build a tab for setting experiment info."""
        expt_frame = ttk.Frame(parent)
        # Control pane along the top
        frame = ttk.Frame(expt_frame)

        ttk.Label(frame, text='Edit experiment:').grid(row=0, column=0, sticky='e')
        experiment = ttk.Combobox(frame, state='readonly', width=15,
                                  values=sorted(self.metadata['experiments'].keys()))
        experiment.bind('<<ComboboxSelected>>',
                        lambda e: self.update_expts_tab(expt_id=experiment.get()))
        experiment.grid(row=0, column=1, sticky='w')
        self.experiment_shown = None
        self.experiment_selector = experiment

        ttk.Label(frame, text='Clone experiment as:').grid(row=1, column=0, sticky='e')
        clone_var = T.StringVar()
        ttk.Entry(frame, textvariable=clone_var, width=15).grid(row=1, column=1, sticky='we')
        self.clone_expt_button = ttk.Button(
            frame, text='Clone',
            command=lambda: self.add_expt(clone_var.get(),
                                          clone=experiment.get()))
        self.clone_expt_button.grid(row=1, column=2, sticky='w')
        if not self.metadata['experiments']:
            self.clone_expt_button.state(['disabled'])

        ttk.Label(frame, text='Add experiment:').grid(row=2, column=0, sticky='e')
        add_var = T.StringVar()
        ttk.Entry(frame, textvariable=add_var, width=15).grid(row=2, column=1, sticky='we')
        ttk.Button(frame, text='Add',
                   command=lambda: self.add_expt(add_var.get())).grid(
            row=2, column=2, sticky='w')

        frame.columnconfigure(0, weight=1)  # Expand at the sides
        frame.columnconfigure(3, weight=1)
        frame.pack(side='top', fill='x', expand=True)
        # Experiment property editing below the control pane; frame per 'item',
        # all in a scrolling canvas
        self.expts_canvas = canvas = T.Canvas(expt_frame, borderwidth=0)
        canvas.pack(side='left', fill='both', expand=True)
        frame = ttk.Frame(canvas)
        scrollbar = ttk.Scrollbar(expt_frame, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.create_window((0, 0), window=frame, anchor='nw')
        frame.bind("<Configure>", self.on_expts_frame_configure)
        # The contents
        self.expts_boxes = {}
        self.make_expts_part(frame, 'description')
        self.make_expts_part(frame, 'optophysiology')
        self.make_stim_frame(frame)
        for part in ['data_collection', 'pharmacology', 'protocol', 'slices', 'stimulus',
                     'subject', 'surgery', 'virus', 'related_publications', 'notes']:
            self.make_expts_part(frame, part)
        # Show current experiment, if any
        if self.metadata['experiments']:
            experiment.set(experiment['values'][0])
            self.update_expts_tab(expt_id=experiment.get())
        # Add to tabs
        parent.add(expt_frame, text='Experiments')
        return expt_frame

    def on_expts_frame_configure(self, event):
        """Reset the scroll region to encompass the inner frame."""
        self.expts_canvas.configure(scrollregion=self.expts_canvas.bbox("all"))

    def add_expt(self, expt_id, clone=None):
        """Create a new experiment and start editing it."""
        existing_expts = self.experiment_selector['values'] or ()
        if expt_id in existing_expts:
            messagebox.showerror(message='The experiment ID "{}" already exists'.format(expt_id))
            return
        if not expt_id or not expt_id[0].isalpha():
            messagebox.showerror(message='An experiment ID must start with a letter')
            return
        if clone is None:
            clone = self.template_expt
        else:
            self.record_expt()
            clone = self.metadata['experiments'][clone]
        self.metadata['experiments'][expt_id] = wrap_dict(clone)
        self.experiment_selector['values'] = sorted(existing_expts + (expt_id,))
        self.experiment_selector.set(expt_id)
        self.session_experiment_box['values'] = self.experiment_selector['values']
        self.update_expts_tab(expt_id)

    def update_expts_tab(self, expt_id):
        """Show the given experiment in the GUI for editing."""
        def do_subfields(box, expt_field):
            for subfield, entry in box.items():
                if isinstance(entry, collections.Mapping):
                    do_subfields(entry, expt_field[subfield])
                else:
                    entry['textvariable'] = expt_field[subfield]
        if expt_id == self.experiment_shown:
            return
        self.record_expt()
        expt = self.metadata['experiments'][expt_id]
        for field, box in self.expts_boxes.items():
            if isinstance(box, T.Text):
                box.delete('1.0', 'end')
                if field in expt:
                    box.insert('1.0', expt[field].get())
            elif isinstance(box, collections.Mapping):
                do_subfields(box, expt[field])
            elif isinstance(box, list):
                for i, item in enumerate(box):
                    do_subfields(item, expt[field][i])
        self.experiment_shown = expt_id
        self.clone_expt_button.state(['!disabled'])

    def record_expt(self):
        """Save the currently shown experiment fields as the selected experiment.

        We only need to worry about Text fields; Entry fields are tracked by their StringVar.
        Fields that are empty are omitted.
        """
        expt_id = self.experiment_shown
        if expt_id is None:
            return
        expt = self.metadata['experiments'][expt_id]
        for field, box in self.expts_boxes.items():
            if isinstance(box, T.Text):
                contents = box.get('1.0', 'end').strip()
                if contents:
                    expt[field] = T.StringVar()
                    expt[field].set(contents)
                elif field in expt:
                    del expt[field]

    def make_label(self, parent, name, row=0, sticky='w', tooltip_text=''):
        """Make the human-friendly label for a form section."""
        name = name.capitalize().replace('_', ' ') + ':'
        label = ttk.Label(parent, text=name)
        label.grid(row=row, column=0, sticky=sticky)
        if len(tooltip_text) > 0:
            Hovertip(label, tooltip_text, hover_delay=1000)  # delay in ms

    def make_expts_part(self, parent, part_name):
        """Make a component frame for the experiment editor."""
        frame = ttk.Frame(parent)
        if isinstance(self.template_expt[part_name], collections.Mapping):
            # This is actually a related group of fields
            self.make_label(frame, part_name)
            self.expts_boxes[part_name] = boxes = {}
            self.make_expts_fields(frame, self.template_expt[part_name], boxes,
                                   self.template_expt_comments[part_name])
        else:
            self.make_label(frame, part_name, tooltip_text=self.template_expt_comments[part_name])
            textbox = T.Text(frame, width=100, height=5, wrap='word')
            textbox.grid(row=1, column=0, sticky='nesw')
            expts_part = self.template_expt[part_name]
            textbox.insert('1.0', expts_part if expts_part is not None else "")
            self.expts_boxes[part_name] = textbox
        frame.pack(side='top', fill='x', expand=True)

    def make_expts_fields(self, frame, template, boxes, comments):
        """Create a related group of fields for an experiment section."""
        for i, field in enumerate(template):
            if isinstance(template[field], collections.Mapping):
                self.make_label(frame, field, row=i + 1, sticky='ne')
                # Another nesting level!
                boxes[field] = {}
                subframe = ttk.Frame(frame)
                for j, subfield in enumerate(template[field]):
                    self.make_label(subframe, subfield, row=j, sticky='e',
                                    tooltip_text=comments[field][subfield])
                    boxes[field][subfield] = ttk.Entry(subframe, width=40)
                    boxes[field][subfield].grid(row=j, column=1, sticky='w')
                subframe.grid(row=i + 1, column=1, sticky='we')
            else:
                tooltip = comments.get(field, '')
                self.make_label(frame, field, row=i + 1, sticky='ne',
                                tooltip_text=tooltip)
                boxes[field] = ttk.Entry(frame, width=70)
                boxes[field].grid(row=i + 1, column=1, sticky='w')

    def make_stim_frame(self, parent):
        """Create fields to edit the stimulus details.

        TODO: At present this restricts you to the same number of stimuli as the template.
        """
        frame = ttk.Frame(parent)
        part_name = 'stimulus_details'
        self.make_label(frame, part_name)
        self.expts_boxes[part_name] = []
        for i, stim in enumerate(self.template_expt[part_name]):
            boxes = {}
            self.expts_boxes[part_name].append(boxes)
            self.make_expts_fields(frame, stim, boxes,
                                   self.template_expt_comments[part_name][i])
        frame.pack(side='top', fill='x', expand=True)


def run_editor():
    '''Run the metadata editor.'''
    app = MetadataEditor()
    app.master.title("Silver Lab NWB Metadata Editor")
    app.lift()  # Raise to top of window stack
    app.mainloop()
