#!/usr/bin/env python3
"""
Past Paper App - Procedural, no classes.

Features:
- Main screen: View Schedule / Start New Paper
- Start New Paper: Random or choose Year/Session/Variant (sample IGCSE Cambridge Maths papers)
- Schedule: adjustable daily target, shows today's progress, last 7 days history
- Paper solver window:
  - Question shown
  - Drawable canvas for working out (pen color & thickness; clear)
  - Entry for final answer
  - Reveal answer from mark scheme
  - Left sidebar: Timer (start/pause/reset), question progress, editor settings
  - Right sidebar: AI chat panel (placeholder)
- Persistence: app_data.json
"""
from datetime import datetime
from tkinter import *
import textwrap
import google.generativeai as genai
from io import StringIO
from markdown import Markdown
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, filedialog
import random
import json
import os
import datetime
import ttkbootstrap as tb

APP_DATA_FILE = "app_data.json"

# ---------------------------
# Sample dataset (small)
# ---------------------------
PAPERS = [
    {
        "year": 2020,
        "session": "May/June",
        "variant": "1",
        "title": "IGCSE Maths 2020 May/June Variant 1",
        "questions": [
            {"text": "Q1. Work out: 24 × 15", "answer": "360"},
            {"text": "Q2. Solve for x: 2x + 5 = 17", "answer": "x = 6"},
            {"text": "Q3. A circle has radius 7 cm. Calculate the area (π = 3.14).", "answer": "Area = 153.86 cm^2"},
        ],
    },
    {
        "year": 2019,
        "session": "Oct/Nov",
        "variant": "2",
        "title": "IGCSE Maths 2019 Oct/Nov Variant 2",
        "questions": [
            {"text": "Q1. Simplify: (3x + 2x) - x", "answer": "4x"},
            {"text": "Q2. Evaluate: 5! (factorial)", "answer": "120"},
            {"text": "Q3. The mean of 5 numbers is 8. Total of numbers?", "answer": "Total = 40"},
        ],
    },
    {
        "year": 2021,
        "session": "May/June",
        "variant": "1",
        "title": "IGCSE Maths 2021 May/June Variant 1",
        "questions": [
            {"text": "Q1. Convert 0.375 to a fraction.", "answer": "3/8"},
            {"text": "Q2. Solve: x^2 = 49", "answer": "x = ±7"},
            {"text": "Q3. A triangle has sides 3, 4, 5. Classify it.", "answer": "Right-angled (Pythagorean triple)"},
        ],
    },
]

# ---------------------------
# Application state (globals)
# ---------------------------
root = None
frames = {}  # name -> Frame

app_data = {}
current_paper = None
q_index = 0

# Timer state
timer_running = False
timer_seconds = 0
timer_job = None

# Canvas editor state
pen_color = "#000000"
pen_thickness = 3
_last_x = None
_last_y = None

# Widgets that need to be referenced across functions
widgets = {}

# ---------------------------
# Persistence helpers
# ---------------------------
def load_app_data():
    default = {
        "daily_target": 1,
        "progress": {},
        "editor": {"color": "#000000", "thickness": 3}
    }
    if os.path.exists(APP_DATA_FILE):
        try:
            with open(APP_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in default:
                if k not in data:
                    data[k] = default[k]
            return data
        except Exception:
            return default
    else:
        return default

def save_app_data():
    global app_data
    try:
        with open(APP_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(app_data, f, indent=2)
    except Exception as e:
        messagebox.showerror("Save error", str(e))

def today_iso():
    return datetime.date.today().isoformat()

# ---------------------------
# UI: screen management
# ---------------------------
def show_screen(name):
    for k, f in frames.items():
        f.grid_forget()
    frames[name].grid(row=0, column=0, sticky="nsew")
    # call on_show if present
    if name == "MainScreen":
        update_main_stats()
    elif name == "ScheduleScreen":
        schedule_on_show()
    elif name == "StartPaperScreen":
        start_paper_on_show()
    elif name == "PaperSolverScreen":
        solver_on_show()

# ---------------------------
# Build screens
# ---------------------------
def build_main_screen(parent):
    f = ttk.Frame(parent)
    frames["MainScreen"] = f

    title = ttk.Label(f, text="PaprAI - The Comprehensive Study Platform", font=("Arial", 18, "bold"))
    title.pack(pady=18)

    btn_frame = ttk.Frame(f)
    btn_frame.pack(pady=10)

    start_btn = ttk.Button(btn_frame, text="Start New Paper", command=lambda: show_screen("StartPaperScreen"))
    start_btn.grid(row=0, column=0, padx=12, pady=12, ipadx=20, ipady=10)

    schedule_btn = ttk.Button(btn_frame, text="View Schedule / Progress", command=lambda: show_screen("ScheduleScreen"))
    schedule_btn.grid(row=0, column=1, padx=12, pady=12, ipadx=20, ipady=10)

    stats_frame = ttk.LabelFrame(f, text="Today's Progress")
    stats_frame.pack(padx=20, pady=20, fill="x")

    widgets["main_progress_var"] = tk.StringVar()
    widgets["main_progress_label"] = ttk.Label(stats_frame, textvariable=widgets["main_progress_var"])
    widgets["main_progress_label"].pack(padx=8, pady=8)

def update_main_stats():
    prog = app_data.get("progress", {}).get(today_iso(), {}).get("papers_solved", 0)
    target = app_data.get("daily_target", 1)
    pct = int((prog / target) * 100) if target > 0 else 0
    widgets["main_progress_var"].set(f"Papers solved today: {prog} / {target} ({pct}%)")

def build_schedule_screen(parent):
    f = ttk.Frame(parent)
    frames["ScheduleScreen"] = f

    top = ttk.Frame(f)
    top.pack(fill="x", padx=12, pady=12)

    back = ttk.Button(top, text="Back", command=lambda: show_screen("MainScreen"))
    back.pack(side="left")

    title = ttk.Label(top, text="Schedule & Daily Target", font=("Arial", 14, "bold"))
    title.pack(side="left", padx=20)

    main = ttk.Frame(f)
    main.pack(fill="both", expand=True, padx=20, pady=10)

    left = ttk.Frame(main)
    left.pack(side="left", fill="both", expand=True)

    tframe = ttk.LabelFrame(left, text="Daily Target (papers)")
    tframe.pack(fill="x", pady=8)
    widgets["target_var"] = tk.IntVar(value=app_data.get("daily_target", 1))
    spin = ttk.Spinbox(tframe, from_=0, to=20, textvariable=widgets["target_var"], width=6)
    spin.pack(side="left", padx=8, pady=8)
    set_btn = ttk.Button(tframe, text="Set", command=schedule_set_target)
    set_btn.pack(side="left", padx=8)

    prog_frame = ttk.LabelFrame(left, text="Today's Progress")
    prog_frame.pack(fill="x", pady=8)
    widgets["schedule_progress_bar"] = ttk.Progressbar(prog_frame, orient="horizontal", length=400, mode="determinate")
    widgets["schedule_progress_bar"].pack(padx=8, pady=8)
    widgets["schedule_progress_label"] = ttk.Label(prog_frame, text="")
    widgets["schedule_progress_label"].pack(padx=8, pady=(0,8))

    hist_frame = ttk.LabelFrame(left, text="Last 7 days")
    hist_frame.pack(fill="both", expand=True, pady=8)
    widgets["hist_list"] = tk.Listbox(hist_frame, height=8)
    widgets["hist_list"].pack(fill="both", expand=True, padx=8, pady=8)

    right = ttk.Frame(main)
    right.pack(side="right", fill="y", padx=8)

    help_label = ttk.Label(right, text="Notes:\n- Track papers solved per day.\n- Use Start New Paper to mark progress when you finish a paper.\n- Progress is saved locally.", justify="left")
    help_label.pack(padx=8, pady=8)

def schedule_on_show():
    widgets["target_var"].set(app_data.get("daily_target", 1))
    refresh_schedule_progress()

def schedule_set_target():
    val = widgets["target_var"].get()
    if val < 0:
        messagebox.showerror("Invalid", "Target must be >= 0")
        return
    app_data["daily_target"] = int(val)
    save_app_data()
    refresh_schedule_progress()
    messagebox.showinfo("Saved", f"Daily target set to {val}")

def refresh_schedule_progress():
    today = today_iso()
    progress = app_data.get("progress", {}).get(today, {}).get("papers_solved", 0)
    target = app_data.get("daily_target", 1)
    pct = int((progress / target) * 100) if target > 0 else 0
    widgets["schedule_progress_bar"]["value"] = min(pct, 100)
    widgets["schedule_progress_label"].config(text=f"{progress} / {target} papers ({pct}%)")

    widgets["hist_list"].delete(0, tk.END)
    for i in range(6, -1, -1):
        d = datetime.date.today() - datetime.timedelta(days=i)
        s = d.isoformat()
        p = app_data.get("progress", {}).get(s, {}).get("papers_solved", 0)
        widgets["hist_list"].insert(tk.END, f"{s}: {p} papers")

# ---------------------------
# Start Paper screen
# ---------------------------
def build_start_paper_screen(parent):
    f = ttk.Frame(parent)
    frames["StartPaperScreen"] = f

    top = ttk.Frame(f)
    top.pack(fill="x", pady=8, padx=8)
    back = ttk.Button(top, text="Back", command=lambda: show_screen("MainScreen"))
    back.pack(side="left")
    title = ttk.Label(top, text="Start New Paper", font=("Arial", 14, "bold"))
    title.pack(side="left", padx=12)

    main = ttk.Frame(f)
    main.pack(fill="both", expand=True, padx=20, pady=16)

    rand_btn = ttk.Button(main, text="Start Random Paper", command=start_random_paper)
    rand_btn.pack(pady=8, ipadx=12, ipady=8)

    sel_frame = ttk.LabelFrame(main, text="Choose Year / Session / Variant")
    sel_frame.pack(fill="x", pady=12)

    ttk.Label(sel_frame, text="Year:").grid(row=0, column=0, padx=6, pady=6, sticky="e")
    ttk.Label(sel_frame, text="Session:").grid(row=1, column=0, padx=6, pady=6, sticky="e")
    ttk.Label(sel_frame, text="Variant:").grid(row=2, column=0, padx=6, pady=6, sticky="e")

    years = sorted(set(p["year"] for p in PAPERS))
    widgets["sp_year_var"] = tk.IntVar(value=years[0] if years else 2020)
    widgets["sp_session_var"] = tk.StringVar()
    widgets["sp_variant_var"] = tk.StringVar()

    widgets["sp_year_cb"] = ttk.Combobox(sel_frame, values=years, textvariable=widgets["sp_year_var"], state="readonly", width=20)
    widgets["sp_year_cb"].grid(row=0, column=1, padx=6, pady=6)
    widgets["sp_year_cb"].bind("<<ComboboxSelected>>", lambda e: sp_refresh_sessions())

    widgets["sp_session_cb"] = ttk.Combobox(sel_frame, values=[], textvariable=widgets["sp_session_var"], state="readonly", width=20)
    widgets["sp_session_cb"].grid(row=1, column=1, padx=6, pady=6)
    widgets["sp_session_cb"].bind("<<ComboboxSelected>>", lambda e: sp_refresh_variants())

    widgets["sp_variant_cb"] = ttk.Combobox(sel_frame, values=[], textvariable=widgets["sp_variant_var"], state="readonly", width=20)
    widgets["sp_variant_cb"].grid(row=2, column=1, padx=6, pady=6)

    start_btn = ttk.Button(sel_frame, text="Start Selected Paper", command=start_selected_paper)
    start_btn.grid(row=3, column=0, columnspan=2, pady=12)

    sp_refresh_sessions()

def start_paper_on_show():
    # update combobox values if needed
    sp_refresh_sessions()

def sp_refresh_sessions():
    years = sorted(set(p["year"] for p in PAPERS))
    y = int(widgets["sp_year_var"].get())
    sessions = sorted(set(p["session"] for p in PAPERS if p["year"] == y))
    widgets["sp_session_cb"]["values"] = sessions
    widgets["sp_session_var"].set(sessions[0] if sessions else "")
    sp_refresh_variants()

def sp_refresh_variants():
    y = int(widgets["sp_year_var"].get())
    s = widgets["sp_session_var"].get()
    variants = sorted(set(p["variant"] for p in PAPERS if p["year"] == y and p["session"] == s))
    widgets["sp_variant_cb"]["values"] = variants
    widgets["sp_variant_var"].set(variants[0] if variants else "")

def start_random_paper():
    paper = random.choice(PAPERS)
    open_solver_with_paper(paper)

def start_selected_paper():
    y = int(widgets["sp_year_var"].get())
    s = widgets["sp_session_var"].get()
    v = widgets["sp_variant_var"].get()
    candidates = [p for p in PAPERS if p["year"] == y and p["session"] == s and p["variant"] == v]
    if not candidates:
        messagebox.showerror("Not found", "No paper matches the selection.")
        return
    open_solver_with_paper(candidates[0])

# ---------------------------
# Paper solver screen
# ---------------------------




def build_paper_solver_screen(parent):



    genai.configure(api_key="AIzaSyBlWEH4hu6zTipDnlrgI_FP4USULu2aefs")
    # Please dear coders don't use my API Key, generate your own FREE one on Google AI Studio
    # This is the free model after all, stealing it will do nothing but prove you're just evil
    model = genai.GenerativeModel("models/gemini-2.0-flash") # I only need text generation here
    # Following code used to remove markdown formatting (credit to Pavel Vorobyov, stackoverflow)
    chat = model.start_chat()


    def unmark_element(element, stream=None):
        if stream is None:
            stream = StringIO()
        if element.text:
            stream.write(element.text)
        for sub in element:
            unmark_element(sub, stream)
        if element.tail:
            stream.write(element.tail)
        return stream.getvalue()
    # patching Markdown
    Markdown.output_formats["plain"] = unmark_element
    __md = Markdown(output_format="plain")
    __md.stripTopLevelTags = False


    def unmark(text):
        return __md.convert(text)

    def getAIResponse(msg):
        prompt = f"{msg} + \n\n Keep answer short and concise, do not use any visual explanations or links"
        response = chat.send_message(prompt, stream=False)
        text = unmark(response.text)
        return text

    def send(event):
        msg = EntryBox.get("1.0", 'end-1c').strip()
        EntryBox.delete("0.0", END)

        if msg != '':
            ChatLog.config(state=NORMAL)
            ChatLog.insert(END, "AI"+' ', ("small", "right", "greycolour"))
            ChatLog.window_create(END, window=Label(ChatLog, fg="#000000", text=msg, 
            wraplength=200, font=("Arial", 10), bg="lightblue", bd=4, justify="left"))
            ChatLog.insert(END,'\n ', "left")
            ChatLog.config(foreground="#0000CC", font=("Helvetica", 9))
            ChatLog.yview(END)

            res = getAIResponse(msg)
            ChatLog.insert(END, "AI"+' ', ("small", "greycolour", "left"))
            ChatLog.window_create(END, window=Label(ChatLog, fg="#000000", text=res, 
            wraplength=200, font=("Arial", 10), bg="#DDDDDD", bd=4, justify="left"))
            ChatLog.insert(END, '\n ', "right")
            ChatLog.config(state=DISABLED)
            ChatLog.yview(END)

    def send_by_button():
        getmsg = EntryBox.get("1.0", 'end-1c').strip()
        msg = textwrap.fill(getmsg,30)
        EntryBox.delete("0.0", END)

        if msg != '':
            ChatLog.config(state=NORMAL)
            ChatLog.insert(END, "AI", ("small","right","colour"))
            ChatLog.insert(END,msg + '\n\n',("right"))

            ChatLog.config(foreground="#0000CC", font=("Helvetica", 9))

            res = getAIResponse
            ChatLog.insert(END, "AI", ("small", "colour"))
            ChatLog.insert(END,textwrap.fill(res,30)+'\n\n')

            ChatLog.config(state=DISABLED)
            ChatLog.yview(END)


    # The following two functions are defined to add a placeholder text or to delete it.
    def deletePlaceholder(event):
        Placeholder.place_forget()
        EntryBox.focus_set()


    def addPlaceholder(event):
        if placeholderFlag == 1:
            Placeholder.place(x=6, y=421, height=70, width=265)

    def update():
        global placeholderFlag
        if (EntryBox.get("1.0", 'end-1c').strip() == ''):
            SendButton['state'] = DISABLED
            placeholderFlag = 1
        elif EntryBox.get("1.0", 'end-1c').strip() != '':
            SendButton['state'] = ACTIVE
            placeholderFlag = 0
        right.after(100, update)
        


    global pen_color, pen_thickness
    f = ttk.Frame(parent)
    frames["PaperSolverScreen"] = f

    top = ttk.Frame(f)
    top.pack(fill="x")
    back = ttk.Button(top, text="Back", command=solver_on_back)
    back.pack(side="left", padx=6, pady=6)
    widgets["solver_title_label"] = ttk.Label(top, text="", font=("Arial", 14, "bold"))
    widgets["solver_title_label"].pack(side="left", padx=16)

    main = ttk.Frame(f)
    main.pack(fill="both", expand=True)

    # Left sidebar
    left = ttk.Frame(main, width=300)
    left.pack(side="left", fill="y", padx=6, pady=6)
    left.pack_propagate(False)

    tframe = ttk.LabelFrame(left, text="Timer")
    tframe.pack(fill="x", pady=6)
    widgets["timer_label"] = ttk.Label(tframe, text="00:00:00", font=("Arial", 12))
    widgets["timer_label"].pack(pady=6)
    timer_btn_frame = ttk.Frame(tframe)
    timer_btn_frame.pack()
    widgets["timer_start_btn"] = ttk.Button(timer_btn_frame, text="Start", command=timer_start)
    widgets["timer_start_btn"].grid(row=0, column=0, padx=4)
    widgets["timer_pause_btn"] = ttk.Button(timer_btn_frame, text="Pause", command=timer_pause, state="disabled")
    widgets["timer_pause_btn"].grid(row=0, column=1, padx=4)
    widgets["timer_reset_btn"] = ttk.Button(timer_btn_frame, text="Reset", command=timer_reset)
    widgets["timer_reset_btn"].grid(row=0, column=2, padx=4)

    qp = ttk.LabelFrame(left, text="Question Progress")
    qp.pack(fill="x", pady=6)
    widgets["qprogress_var"] = tk.StringVar()
    ttk.Label(qp, textvariable=widgets["qprogress_var"]).pack(padx=6, pady=8)
    nav = ttk.Frame(qp)
    nav.pack(pady=6)
    widgets["prev_btn"] = ttk.Button(nav, text="Prev", command=solver_prev_question)
    widgets["prev_btn"].grid(row=0, column=0, padx=4)
    widgets["next_btn"] = ttk.Button(nav, text="Next", command=solver_next_question)
    widgets["next_btn"].grid(row=0, column=1, padx=4)
    finish_btn = ttk.Button(qp, text="Finish Paper", command=solver_finish_paper)
    finish_btn.pack(pady=6)

    ed = ttk.LabelFrame(left, text="Editor Settings")
    ed.pack(fill="x", pady=6)
    ttk.Label(ed, text="Pen color:").pack(anchor="w", padx=6, pady=(6,0))
    widgets["color_btn"] = ttk.Button(ed, text="Choose Color", command=choose_pen_color)
    widgets["color_btn"].pack(fill="x", padx=6, pady=4)
    ttk.Label(ed, text="Thickness:").pack(anchor="w", padx=6, pady=(6,0))
    widgets["thickness_var"] = tk.IntVar(value=app_data.get("editor", {}).get("thickness", 3))
    thickness_spin = ttk.Spinbox(ed, from_=1, to=20, textvariable=widgets["thickness_var"], width=6, command=update_editor_settings)
    thickness_spin.pack(padx=6, pady=4)
    clear_btn = ttk.Button(ed, text="Clear Canvas", command=solver_clear_canvas)
    clear_btn.pack(fill="x", padx=6, pady=6)

    # Center
    center = ttk.Frame(main)
    center.pack(side="left", fill="both", expand=True, padx=6, pady=6)

    qframe = ttk.LabelFrame(center, text="Question")
    qframe.pack(fill="x", pady=6)
    widgets["question_text"] = tk.Text(qframe, height=5, wrap="word", state="disabled")
    widgets["question_text"].pack(fill="x", padx=6, pady=6)

    canvas_frame = ttk.LabelFrame(center, text="Working Out (canvas)")
    canvas_frame.pack(fill="both", expand=True, pady=6)
    widgets["canvas"] = tk.Canvas(canvas_frame, bg="white")
    widgets["canvas"].pack(fill="both", expand=True, padx=6, pady=6)
    widgets["canvas"].bind("<B1-Motion>", solver_canvas_draw)
    widgets["canvas"].bind("<ButtonRelease-1>", lambda e: solver_canvas_release())

    ansframe = ttk.Frame(center)
    ansframe.pack(fill="x", pady=6)
    ttk.Label(ansframe, text="Final Answer:").pack(side="left", padx=6)
    widgets["answer_var"] = tk.StringVar()
    ans_entry = ttk.Entry(ansframe, textvariable=widgets["answer_var"], width=40)
    ans_entry.pack(side="left", padx=6)
    reveal_btn = ttk.Button(ansframe, text="Reveal Answer", command=solver_reveal_answer)
    reveal_btn.pack(side="left", padx=6)

    # Right sidebar: AI chat
    right = ttk.Frame(main, width=400)
    right.pack(side="right", fill="y", padx=6, pady=6)
    right.pack_propagate(False)


    # Create Chat window
    ChatLog = Text(right, bd=0, height="8", width="50", font="Helvetica", wrap="word")
    ChatLog.config(state=NORMAL)
    ChatLog.tag_config("right", justify="right")
    ChatLog.tag_config("small", font=("Helvetica", 7))
    ChatLog.tag_config("colour", foreground="#333333")
    ChatLog.insert(END, "AI", ("small","colour"))
    ChatLog.insert(END,textwrap.fill(f"Hello student, How can I assist you?",30))
    ChatLog.insert(END,'\n')
    ChatLog.config(foreground="#0000CC", font=("Helvetica", 9))
    ChatLog.config(state=DISABLED)
    ChatLog.tag_config("left", justify="left")

    # Bind scrollbar to Chat window
    scrollbar = Scrollbar(right, command=ChatLog.yview, cursor="double_arrow")
    ChatLog['yscrollcommand'] = scrollbar.set

    # Create Button to send message
    SendButton = Button(right, font=("Comic Sans MS", 12, 'bold'), text="Send", width="8", height=5,
                        bd=0, fg="#750216", activebackground="#AAAAAA", bg="#999999", command=send_by_button)

    # Create the box to enter message
    EntryBox = Text(right, bd=0, fg="#000000", bg="#fff5f5", highlightcolor="#750216",
                    width="29", height="5", font=("Arial",10), wrap="word")

    #Placeholder config and text:
    Placeholder = Text(right, bd=0, fg="#A0A0A0", bg="#fff5f5", highlightcolor="#750216",
                    width="29", height="5", font=("Arial",10), wrap="word")
    Placeholder.insert("1.0", "Ask a question (eg: What is Pythagoras Theorem?)")

    # Place all components on the screen
    scrollbar.place(x=376, y=6, height=406)
    ChatLog.place(x=6, y=6, height=410, width=370)
    EntryBox.place(x=6, y=421, height=70, width=276)
    SendButton.place(x=282, y=421, height=70)
    Placeholder.place(x=6, y=421, height=70, width=276)

    Placeholder.bind("<FocusIn>", deletePlaceholder)
    EntryBox.bind("<FocusOut>", addPlaceholder)
    EntryBox.bind("<Return>", send)

    update()


    

    bottom = ttk.Frame(f)
    bottom.pack(fill="x", padx=6, pady=6)
    save_canvas_btn = ttk.Button(bottom, text="Save Canvas to PS", command=solver_save_canvas_to_file)
    save_canvas_btn.pack(side="right")

def open_solver_with_paper(paper):
    global current_paper, q_index, pen_color, pen_thickness
    current_paper = paper
    q_index = 0
    widgets["solver_title_label"].config(text=paper.get("title", ""))
    # load editor settings
    pen_color = app_data.get("editor", {}).get("color", "#000000")
    pen_thickness = app_data.get("editor", {}).get("thickness", 3)
    widgets["thickness_var"].set(pen_thickness)
    solver_load_question()
    # reset timer
    timer_reset()
    widgets["timer_start_btn"].config(state="normal")
    widgets["timer_pause_btn"].config(state="disabled")
    show_screen("PaperSolverScreen")

def solver_on_show():
    # ensure widgets reflect current state
    solver_load_question()

def solver_load_question():
    global _last_x, _last_y
    if not current_paper:
        return
    questions = current_paper.get("questions", [])
    qcount = len(questions)
    if qcount == 0:
        return
    idx = max(0, min(q_index, qcount - 1))
    q = questions[idx]
    widgets["question_text"].config(state="normal")
    widgets["question_text"].delete("1.0", tk.END)
    widgets["question_text"].insert(tk.END, q.get("text", ""))
    widgets["question_text"].config(state="disabled")
    widgets["qprogress_var"].set(f"Question {idx+1} / {qcount}")
    widgets["answer_var"].set("")
    solver_clear_canvas()
    # nav state
    widgets["prev_btn"].config(state="normal" if idx > 0 else "disabled")
    widgets["next_btn"].config(state="normal" if idx < qcount - 1 else "disabled")

def solver_prev_question():
    global q_index
    if q_index > 0:
        q_index -= 1
        solver_load_question()

def solver_next_question():
    global q_index
    if current_paper and q_index < len(current_paper.get("questions", [])) - 1:
        q_index += 1
        solver_load_question()

def solver_finish_paper():
    if not current_paper:
        return
    if messagebox.askyesno("Finish Paper", "Mark this paper as finished and record progress?"):
        s = app_data.setdefault("progress", {})
        today = today_iso()
        rec = s.setdefault(today, {})
        rec["papers_solved"] = rec.get("papers_solved", 0) + 1
        save_app_data()
        messagebox.showinfo("Recorded", "Paper recorded as finished in today's progress.")
        show_screen("MainScreen")

def solver_on_back():
    if current_paper and messagebox.askyesno("Leave", "Return to main screen? Current session will remain unsaved unless you finish the paper."):
        show_screen("MainScreen")

# ---------------------------
# Timer functions
# ---------------------------
def format_time(secs):
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def timer_tick():
    global timer_seconds, timer_job
    timer_seconds += 1
    widgets["timer_label"].config(text=format_time(timer_seconds))
    timer_job = root.after(1000, timer_tick)

def timer_start():
    global timer_running, timer_job
    if not timer_running:
        timer_running_state_set(True)
        timer_job = root.after(1000, timer_tick)

def timer_pause():
    global timer_running, timer_job
    if timer_running:
        timer_running_state_set(False)
        if timer_job:
            root.after_cancel(timer_job)
            timer_job = None

def timer_reset():
    global timer_seconds, timer_running, timer_job
    if timer_job:
        root.after_cancel(timer_job)
    timer_job = None
    timer_running_state_set(False)
    timer_seconds = 0
    widgets["timer_label"].config(text=format_time(timer_seconds))

def timer_running_state_set(state):
    global timer_running
    timer_running = state
    if state:
        widgets["timer_start_btn"].config(state="disabled")
        widgets["timer_pause_btn"].config(state="normal")
    else:
        widgets["timer_start_btn"].config(state="normal")
        widgets["timer_pause_btn"].config(state="disabled")

# ---------------------------
# Canvas drawing and editor
# ---------------------------
def solver_canvas_draw(event):
    global _last_x, _last_y, pen_color, pen_thickness
    x, y = event.x, event.y
    if _last_x is None:
        _last_x, _last_y = x, y
        return
    w = int(widgets["thickness_var"].get())
    color = pen_color or app_data.get("editor", {}).get("color", "#000000")
    widgets["canvas"].create_line(_last_x, _last_y, x, y, width=w, capstyle=tk.ROUND, smooth=True, fill=color)
    _last_x, _last_y = x, y

def solver_canvas_release():
    global _last_x, _last_y
    _last_x = None
    _last_y = None

def solver_clear_canvas():
    widgets["canvas"].delete("all")
    solver_canvas_release()

def choose_pen_color():
    global pen_color
    col = colorchooser.askcolor(title="Choose pen color", initialcolor=app_data.get("editor", {}).get("color", "#000000"))
    if col and col[1]:
        pen_color = col[1]
        app_data.setdefault("editor", {})["color"] = col[1]
        save_app_data()

def update_editor_settings():
    app_data.setdefault("editor", {})["thickness"] = int(widgets["thickness_var"].get())
    save_app_data()

# ---------------------------
# Reveal answer
# ---------------------------
def solver_reveal_answer():
    if not current_paper:
        return
    q = current_paper.get("questions", [])[q_index]
    ans = q.get("answer", "(no answer)")
    messagebox.showinfo("Mark scheme answer", ans)

# ---------------------------
# AI chat placeholder
# ---------------------------
def solver_send_chat():
    msg = widgets["chat_input_var"].get().strip()
    if not msg:
        return
    solver_append_chat("You: " + msg)
    widgets["chat_input_var"].set("")
    # Placeholder for user integration:
    # Replace the following with your API call. If you use network calls, run them in a background thread
    # and then call solver_append_chat("AI: " + response_text) on the main thread via root.after(...)
    solver_append_chat("AI: [placeholder response — replace solver_send_chat() body with your API call and response handling]")

def solver_append_chat(text):
    widgets["chat_display"].config(state="normal")
    widgets["chat_display"].insert(tk.END, text + "\n")
    widgets["chat_display"].see(tk.END)
    widgets["chat_display"].config(state="disabled")

# ---------------------------
# Canvas saving
# ---------------------------
def solver_save_canvas_to_file():
    try:
        fname = filedialog.asksaveasfilename(defaultextension=".ps", filetypes=[("PostScript", "*.ps"), ("All files", "*.*")], title="Save canvas as PostScript")
        if not fname:
            return
        widgets["canvas"].postscript(file=fname)
        messagebox.showinfo("Saved", f"Canvas saved as PostScript: {fname}\nConvert to PNG/EPS with external tool if needed.")
    except Exception as e:
        messagebox.showerror("Save failed", str(e))

# ---------------------------
# Helpers to open solver
# ---------------------------
def open_solver_with_paper(paper):
    open_solver_with_paper_inner(paper)  # to satisfy linter; actual implementation below

def open_solver_with_paper_inner(paper):
    open_solver_with_paper_impl(paper)

def open_solver_with_paper_impl(paper):
    # wrapper to avoid name collision with previously declared function
    global current_paper, q_index, pen_color, pen_thickness
    current_paper = paper
    q_index = 0
    widgets["solver_title_label"].config(text=paper.get("title", ""))
    # load editor settings
    pen_color = app_data.get("editor", {}).get("color", "#000000")
    pen_thickness = app_data.get("editor", {}).get("thickness", 3)
    widgets["thickness_var"].set(pen_thickness)
    solver_load_question()
    # reset timer
    timer_reset()
    widgets["timer_start_btn"].config(state="normal")
    widgets["timer_pause_btn"].config(state="disabled")
    show_screen("PaperSolverScreen")

# Because of the multiple wrappers above, ensure the single usable function name:
open_solver_with_paper = open_solver_with_paper_impl

# ---------------------------
# Application bootstrap
# ---------------------------
def initialize_ui():
    global root
    root.title("Past Paper App - IGCSE Cambridge Maths")
    root.geometry("1100x700")
    root.minsize(1000, 650)

    container = ttk.Frame(root)
    container.pack(fill="both", expand=True)
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)

    build_main_screen(container)
    build_schedule_screen(container)
    build_start_paper_screen(container)
    build_paper_solver_screen(container)

    show_screen("MainScreen")

def main():
    global root, app_data
    root = tb.Window(themename="yeti")
    app_data = load_app_data()
    initialize_ui()
    root.protocol("WM_DELETE_WINDOW", on_exit)
    root.mainloop()

def on_exit():
    # ensure persistence before exit
    save_app_data()
    root.destroy()

if __name__ == "__main__":
    main()
