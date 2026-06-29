import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt, seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
import warnings; warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid"); plt.rcParams["figure.dpi"]=120
TYPES=["BEEF","PIG","POULTRY","SHEEP"]
EF={"BEEF":99.48,"SHEEP":39.72,"PIG":12.31,"POULTRY":9.87}   # Poore & Nemecek 2018, kg CO2e/kg (via OWID)

m=pd.read_csv("data/oecd_meat.csv"); m.columns=[c.strip().strip("\ufeff") for c in m.columns]
m=m[["LOCATION","SUBJECT","MEASURE","TIME","Value"]].dropna()
AGG={"WLD","OECD","BRICS","EU27","EU28","NONOECD","EU"}
kcap=m[m.MEASURE=="KG_CAP"].pivot_table(index=["LOCATION","TIME"],columns="SUBJECT",values="Value").reset_index()
tonn=m[m.MEASURE=="THND_TONNE"].pivot_table(index=["LOCATION","TIME"],columns="SUBJECT",values="Value").reset_index()
for d in (kcap,tonn):
    for t in TYPES:
        if t not in d: d[t]=np.nan
for t in TYPES: tonn[t+"_co2"]=tonn[t]*EF[t]*1e-3
tonn["total_meat_kt"]=tonn[TYPES].sum(axis=1); tonn["total_co2_Mt"]=tonn[[t+"_co2" for t in TYPES]].sum(axis=1)

# FIG1 per-capita by type (world)
w=kcap[kcap.LOCATION=="WLD"].set_index("TIME")[TYPES]
plt.figure(figsize=(8,4.5))
for t in TYPES: plt.plot(w.index,w[t],marker="o",ms=3,label=t.title())
plt.title("World meat consumption per capita by type\n(the structural shift to poultry)")
plt.ylabel("kg per person / year"); plt.xlabel("Year"); plt.legend(); plt.tight_layout()
plt.savefig("figures/01_percapita_by_type.png"); plt.close()

# FIG2 volume vs footprint share (2020)
wt=tonn[tonn.LOCATION=="WLD"].sort_values("TIME"); latest=wt[wt.TIME==2020].iloc[0]
comp=pd.DataFrame({"Share of volume":{t:latest[t]/latest.total_meat_kt*100 for t in TYPES},
                   "Share of carbon footprint":{t:latest[t+"_co2"]/latest.total_co2_Mt*100 for t in TYPES}})
comp.index=[i.title() for i in comp.index]
plt.figure(figsize=(7.5,4.5)); comp.plot(kind="bar",ax=plt.gca(),color=["#4c72b0","#c44e52"])
plt.title("Beef: ~a fifth of meat volume, two-thirds of meat emissions (World, 2020)")
plt.ylabel("% of total"); plt.xticks(rotation=0); plt.tight_layout(); plt.savefig("figures/02_volume_vs_footprint.png"); plt.close()
print("2020 volume vs footprint share (%):\n",comp.round(1).to_string())

# FIG3 footprint over time by type
plt.figure(figsize=(8,4.5))
plt.stackplot(wt.TIME,[wt[t+"_co2"] for t in TYPES],labels=[t.title() for t in TYPES],
              colors=["#c44e52","#dd8452","#4c72b0","#937860"])
plt.title("Estimated GHG footprint of world meat demand, by type"); plt.ylabel("Mt CO2e / year"); plt.xlabel("Year")
plt.legend(loc="upper left"); plt.tight_layout(); plt.savefig("figures/03_footprint_over_time.png"); plt.close()

# CLUSTERING on meat-mix shares (2018); report mix-intensity (CO2/kg) AND absolute per-capita
ry=2018
cc=kcap[(~kcap.LOCATION.isin(AGG))&(kcap.TIME==ry)].dropna(subset=TYPES).copy()
cc["total"]=cc[TYPES].sum(axis=1)
for t in TYPES: cc[t+"_sh"]=cc[t]/cc["total"]
feat=[t+"_sh" for t in TYPES]
cc["cluster"]=KMeans(n_clusters=4,n_init=10,random_state=42).fit_predict(StandardScaler().fit_transform(cc[feat]))
for t in TYPES: cc[t+"_co2pc"]=cc[t]*EF[t]
cc["co2_pc"]=cc[[t+"_co2pc" for t in TYPES]].sum(axis=1)
cc["co2_per_kg_meat"]=cc["co2_pc"]/cc["total"]
prof=cc.groupby("cluster").agg(n=("LOCATION","size"),beef_sh=("BEEF_sh","mean"),pig_sh=("PIG_sh","mean"),
      poultry_sh=("POULTRY_sh","mean"),sheep_sh=("SHEEP_sh","mean"),
      total_kg=("total","mean"),co2_per_kg=("co2_per_kg_meat","mean"),co2_pc=("co2_pc","mean")
      ).round(2).sort_values("co2_per_kg")
print("\nMeat-mix clusters (2018), sorted by mix carbon intensity (CO2e per kg of meat):")
print(prof.to_string())
plt.figure(figsize=(7.5,5.5))
sc=plt.scatter(cc.POULTRY_sh*100,cc.BEEF_sh*100,c=cc.co2_per_kg_meat,s=45,cmap="YlOrRd",edgecolor="k",linewidths=.3)
plt.colorbar(sc,label="kg CO2e per kg of meat (mix intensity)")
for _,r in cc.iterrows():
    if r.co2_per_kg_meat>cc.co2_per_kg_meat.quantile(.85) or r.co2_per_kg_meat<cc.co2_per_kg_meat.quantile(.12):
        plt.annotate(r.LOCATION,(r.POULTRY_sh*100,r.BEEF_sh*100),fontsize=7,alpha=.8)
plt.xlabel("Poultry share of meat diet (%)"); plt.ylabel("Beef share of meat diet (%)")
plt.title("Meat-diet archetypes: beef-heavy mixes are far more carbon-intense")
plt.tight_layout(); plt.savefig("figures/04_clusters.png"); plt.close()

# FORECAST validation: total (flat -> baseline wins) vs poultry (rising -> trend wins)
def validate(series_col,ax,title):
    s=kcap[kcap.LOCATION=="WLD"].copy()
    s["val"]=s[series_col] if series_col in TYPES else s[TYPES].sum(axis=1)
    h=s[s.TIME<=2019]; tr=h[h.TIME<=2014]; te=h[(h.TIME>=2015)]
    lr=LinearRegression().fit(tr[["TIME"]],tr["val"]); pr=lr.predict(te[["TIME"]])
    base=np.repeat(tr["val"].iloc[-1],len(te))
    mae_lr=mean_absolute_error(te["val"],pr); mae_b=mean_absolute_error(te["val"],base)
    fut=pd.DataFrame({"TIME":range(2010,2029)})
    ax.plot(h.TIME,h.val,"o-",ms=3,label="Actual")
    ax.plot(fut.TIME,lr.predict(fut[["TIME"]]),"--",color="grey",label="Linear trend")
    ax.axvspan(2015,2019,color="orange",alpha=.12)
    ax.set_title(f"{title}\ntrend MAE={mae_lr:.2f} vs naive MAE={mae_b:.2f} kg"); ax.set_xlabel("Year"); ax.legend(fontsize=8)
    return mae_lr,mae_b
fig,(a1,a2)=plt.subplots(1,2,figsize=(12,4.5))
t_lr,t_b=validate("TOTAL",a1,"Total meat / capita (≈flat)"); a1.set_ylabel("kg per person/yr")
p_lr,p_b=validate("POULTRY",a2,"Poultry / capita (rising, then slowing)")
plt.tight_layout(); plt.savefig("figures/05_forecast.png"); plt.close()
print(f"\nForecast (5-yr-ahead, test 2015-2019) — benchmarked against a naive last-value baseline:")
print(f"  Total meat : trend MAE {t_lr:.2f} vs naive {t_b:.2f}  -> naive wins (series is flat)")
print(f"  Poultry    : trend MAE {p_lr:.2f} vs naive {p_b:.2f}  -> naive wins too (growth slowed; linear trend overshoots)")
print("  Lesson: for smooth aggregate series, a naive baseline is a strong benchmark; simple extrapolation is risky.")

# SCENARIO
b=latest["BEEF"]; shift=0.25*b; base_co2=latest.total_co2_Mt
new_co2=base_co2-shift*EF["BEEF"]*1e-3+shift*EF["POULTRY"]*1e-3; red=(base_co2-new_co2)/base_co2*100
print(f"\nScenario: shift 25% of world beef volume to poultry (2020): {base_co2:.0f} -> {new_co2:.0f} Mt CO2e ({red:.1f}% cut)")

# MULTI-SOURCE: meat-mix intensity vs national methane (OWID, 2018)
ow=pd.read_csv("data/owid_emissions_subset.csv"); iso=ow[ow.year==2018][["iso_code","methane","population"]].dropna()
mrg=cc.merge(iso,left_on="LOCATION",right_on="iso_code",how="inner")
mrg["methane_pc"]=mrg["methane"]/mrg["population"]*1e6
r=mrg[["co2_pc","methane_pc"]].corr().iloc[0,1]
print(f"\nMulti-source: corr(meat CO2e/capita, national methane/capita) = {r:.2f} (n={len(mrg)})")
plt.figure(figsize=(7,5))
sns.regplot(data=mrg,x="co2_pc",y="methane_pc",scatter_kws={"s":35,"edgecolor":"k"})
plt.xlabel("Estimated meat CO2e per capita (kg)"); plt.ylabel("National methane per capita (t, OWID)")
plt.title(f"Meat-diet carbon intensity vs national methane (2018), r={r:.2f}")
plt.tight_layout(); plt.savefig("figures/06_multisource.png"); plt.close()

tonn.to_csv("data/meat_footprint_by_country_year.csv",index=False)
cc[["LOCATION","total","co2_pc","co2_per_kg_meat","cluster"]+feat].to_csv("data/country_clusters_2018.csv",index=False)
print("\nAll 6 figures + 2 data artifacts saved. DONE.")
