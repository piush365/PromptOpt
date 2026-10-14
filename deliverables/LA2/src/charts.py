import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import sys
out=sys.argv[1]
BEFORE="#C8553D"; AFTER="#1F6F8B"; GREY="#8A8F98"; INK="#1D2433"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":12,"axes.spines.top":False,"axes.spines.right":False,"axes.edgecolor":"#9AA0A6","axes.labelcolor":INK,"xtick.color":INK,"ytick.color":INK})
def save(fig,name): fig.tight_layout(); fig.savefig(f"{out}/{name}.png",dpi=200); plt.close(fig)

# 1 tokens per category
cats=["closed_qa","info_extraction","classification","summarization","coding","all"]
deg=[1115,875,488,1169,903,909]; opt=[417,466,278,552,324,406]; ch=["-44.5%","-24.2%","-28.5%","-43.3%","-54.7%","-39.2%"]
fig,ax=plt.subplots(figsize=(10,4.8)); import numpy as np; x=np.arange(len(cats)); w=0.38
ax.bar(x-w/2,deg,w,color=BEFORE,label="Vague (degraded) prompt"); ax.bar(x+w/2,opt,w,color=AFTER,label="Optimized (Stage A+B)")
for i in range(len(cats)): ax.text(x[i]+w/2,opt[i]+25,ch[i],ha="center",fontsize=11,color=AFTER,fontweight="bold")
ax.set_xticks(x,cats); ax.set_ylabel("Mean total tokens per prompt"); ax.legend(frameon=False)
ax.set_title("Total tokens (input + output), test split n = 482, gpt-oss-120b",fontsize=12,color=INK)
save(fig,"chart_tokens")

# 2 correctness
c2=["closed_qa","info_extraction","classification","summarization","coding","overall"]
v=[8,7,7,7,8,37]; o=[10,10,8,5,9,42]; n=[10,10,10,10,10,50]
fig,ax=plt.subplots(figsize=(10,4.6)); x=np.arange(len(c2))
vp=[a/b*100 for a,b in zip(v,n)]; op=[a/b*100 for a,b in zip(o,n)]
ax.bar(x-w/2,vp,w,color=BEFORE,label="Vague prompt"); ax.bar(x+w/2,op,w,color=AFTER,label="Optimized prompt")
for i in range(len(c2)):
    ax.text(x[i]-w/2,vp[i]+2,f"{v[i]}/{n[i]}",ha="center",fontsize=10); ax.text(x[i]+w/2,op[i]+2,f"{o[i]}/{n[i]}",ha="center",fontsize=10)
ax.set_ylim(0,115); ax.set_xticks(x,c2); ax.set_ylabel("Correct answers (%)"); ax.legend(frameon=False,loc="upper left",ncol=2)
ax.set_title("Correctness suite: 50 hand-written cases, gpt-oss-120b on Groq",fontsize=12,color=INK)
save(fig,"chart_correctness")

# 3 stage A F1
fig,ax=plt.subplots(figsize=(9,3.8))
cc=["coding","classification","closed_qa","info_extraction","summarization"]; f1=[0.98,0.94,0.65,0.63,0.51]
ax.barh(cc[::-1],f1[::-1],color=[GREY,GREY,AFTER,AFTER][:0] or AFTER)
for i,val in enumerate(f1[::-1]): ax.text(val+0.01,i,f"{val:.2f}",va="center")
ax.set_xlim(0,1.1); ax.set_xlabel("F1 score (test, 482 prompts); accuracy 74.7%")
save(fig,"chart_stage_a")

# 4 tests per module
mods=[("Image mode (v1+v2)",215),("Stage B rules",113+10),("Rendering + pipeline",77),("Evaluation harness",62+7+3+2),("Dataset tooling",32+29+27+19),("Stage A",47),("API + UI API",29+8),("Stage C contract/parse",18+12),("Database layer",22),("Coding sandbox",21),("Correctness suite",17),("Compare + providers",9+7),("Spelling + demo",5+7)]
mods.sort(key=lambda t:t[1])
fig,ax=plt.subplots(figsize=(9,5.2))
ax.barh([m for m,_ in mods],[c for _,c in mods],color=AFTER)
for i,(_,c) in enumerate(mods): ax.text(c+2,i,str(c),va="center",fontsize=10)
ax.set_xlabel("pytest tests (798 total, all passing)")
save(fig,"chart_tests")

# 5 commit timeline
weeks=["W33\n10-16 Aug","W34\n17-23 Aug","W35-38\n24 Aug-20 Sep","W39\n21-27 Sep","W40\n28 Sep-4 Oct","W41\n5-11 Oct"]; cnt=[4,3,0,33,22,30]
fig,ax=plt.subplots(figsize=(10,4.2)); ax.bar(weeks,cnt,color=AFTER)
for i,c in enumerate(cnt): ax.text(i,c+0.6,str(c),ha="center")
ax.set_ylabel("Commits (all branches)"); ax.set_title("92 commits, 13 Aug - 10 Oct 2026",fontsize=12,color=INK)
for lab,xi in [("frozen-for-test\n27 Sep",3),("final-for-test 2 Oct",4),("v1.0 8 Oct",5)]: pass
save(fig,"chart_commits")

# 6 benchmark
fig,axs=plt.subplots(1,3,figsize=(10,3.6))
for ax,(t,a,b,fmt) in zip(axs,[("Quality (0-10)",8.2,9.0,"{:.1f}"),("Task success (%)",67,85,"{:.0f}%"),("Total tokens",894,386,"{:.0f}")]):
    ax.bar(["Vague","Stage B"],[a,b],color=[BEFORE,AFTER]); ax.set_title(t,fontsize=12)
    for i,val in enumerate([a,b]): ax.text(i,val*1.02,fmt.format(val),ha="center")
    ax.set_ylim(0,max(a,b)*1.2)
fig.suptitle("Benchmark split (44 prompts), target gpt-oss-120b, blind judge",fontsize=12)
save(fig,"chart_benchmark")

# ---- diagrams
def box(ax,x,y,w,h,text,fc="#EEF3F8",ec="#1F3A5F",fs=10.5,bold=False):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.02,rounding_size=0.12",fc=fc,ec=ec,lw=1.4))
    ax.text(x+w/2,y+h/2,text,ha="center",va="center",fontsize=fs,color=INK,fontweight="bold" if bold else "normal",wrap=True)
def arrow(ax,x1,y1,x2,y2,label=None,color="#374151"):
    ax.annotate("",xy=(x2,y2),xytext=(x1,y1),arrowprops=dict(arrowstyle="-|>",color=color,lw=1.4))
    if label: ax.text((x1+x2)/2,(y1+y2)/2+0.12,label,ha="center",fontsize=9,color="#4B5563")

# transaction flow
fig,ax=plt.subplots(figsize=(13,7.2)); ax.set_xlim(0,13); ax.set_ylim(0,7.2); ax.axis("off")
steps=[(0.2,5.6,"1. User submits\nprompt + target LLM +\ncategory + attachment","#FFF4E5"),
       (2.8,5.6,"2. POST /api/optimize\nenforce_retention\n(purge expired)","#EEF3F8"),
       (5.4,5.6,"3. create_prompt\nPII scrub, expires_at\n(prompts)","#E8F5EE"),
       (8.0,5.6,"4. Stage A\nsave_features\n(prompt_features)","#E8F5EE"),
       (10.6,5.6,"5. Stage B (+C if routed)\nsave_optimization\n(optimization_results,\ntransformations)","#E8F5EE")]
for x,y,t,c in steps: box(ax,x,y,2.3,1.3,t,fc=c,fs=10)
for i in range(4): arrow(ax,steps[i][0]+2.3,6.25,steps[i+1][0],6.25)
box(ax,10.6,3.6,2.3,1.3,"6. Render IR\nsave_renderings\nsave_token_usage\n(renderings, token_usage)",fc="#E8F5EE",fs=10)
arrow(ax,11.75,5.6,11.75,4.9)
box(ax,7.6,3.6,2.4,1.3,"7. db.commit()\nONE commit per request\n(failure => nothing stored)",fc="#1F3A5F",ec="#1F3A5F",fs=10)
ax.texts[-1].set_color("white")
arrow(ax,10.6,4.25,10.0,4.25)
box(ax,4.6,3.6,2.4,1.3,"8. JSON response\nfeatures, rules fired,\nrenderings, tokens",fc="#EEF3F8",fs=10)
arrow(ax,7.6,4.25,7.0,4.25)
box(ax,1.0,3.6,2.9,1.3,"9. Compare (optional)\nPOST /api/compare\noriginal vs optimized on\nthe same model",fc="#FFF4E5",fs=10)
arrow(ax,4.6,4.25,3.9,4.25)
box(ax,1.0,1.2,2.9,1.4,"10. History\nGET /api/ui/history\nsearch, view, delete\n(cascade)",fc="#FFF4E5",fs=10)
arrow(ax,2.45,3.6,2.45,2.6)
box(ax,4.6,1.2,4.0,1.4,"11. Retention\nexpires_at = created_at + 30 days\nauto-purge before every request;\npython -m app.init_db --purge",fc="#FDECEA",fs=10)
arrow(ax,3.9,1.9,4.6,1.9)
box(ax,9.4,1.0,3.4,1.8,"repository.py is the ONLY\nmodule that reads/writes\nthe database. Functions flush,\nthe caller commits once.",fc="#F3F4F6",ec="#6B7280",fs=10)
save(fig,"diag_transaction")

# module diagram
fig,ax=plt.subplots(figsize=(13,7.6)); ax.set_xlim(0,13); ax.set_ylim(0,7.6); ax.axis("off")
layers=[(6.3,"Presentation","React + TypeScript UI: Optimize, Compare, Test suite, Results, How it works, History, Image mode, Status","#FFF4E5"),
        (5.1,"API","FastAPI: app/api.py (optimize, compare, history)  ·  app/ui_api.py (status, results, history search/delete)","#EEF3F8")]
for y,t,d,c in layers:
    box(ax,0.2,y,12.6,0.95,"",fc=c); ax.text(0.45,y+0.62,t,fontsize=11.5,fontweight="bold",color=INK); ax.text(0.45,y+0.25,d,fontsize=10.5,color=INK)
mods=[("Stage A\napp/stage_a\nfeatures + category",0.2),("Stage B\napp/stage_b\nrules B01-B16, IR",2.35),("Stage C\napp/stage_c\nLoRA + contract",4.5),("Rendering\napp/rendering.py\nGPT / Claude / Gemini",6.65),("Image mode\napp/image\nv2 rules + renderers",8.8),("Compare\napp/compare\nproviders, judge",10.95)]
ax.text(0.2,4.75,"Core modules (app/pipeline.py runs one request end to end)",fontsize=11,fontweight="bold",color=INK)
for t,x in mods: box(ax,x,3.25,1.85,1.35,t,fc="#E8F5EE",fs=9.8)
sup=[("Coding sandbox\napp/coding (bwrap)",0.2),("Evaluation harness\napp/evaluation, correctness",3.3),("Spelling\napp/spelling.py",6.4),("LLM clients + budget\nGroq / Cerebras / Gemini",9.5)]
ax.text(0.2,2.85,"Supporting modules",fontsize=11,fontweight="bold",color=INK)
for t,x in sup: box(ax,x,1.85,2.9,0.9,t,fc="#F3F4F6",ec="#6B7280",fs=9.8)
box(ax,0.2,0.2,12.6,1.2,"",fc="#1F3A5F")
ax.text(6.5,0.95,"Data layer: models.py (10 tables) · repository.py (only reader/writer) · pii.py · SQLite / PostgreSQL",ha="center",color="white",fontsize=10.5,fontweight="bold")
ax.text(6.5,0.5,"prompts · prompt_features · optimization_results · transformations · renderings · token_usage · rules · lora_models · users · eval_runs",ha="center",color="white",fontsize=9.2)
save(fig,"diag_modules")
print("done")
