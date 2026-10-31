# Demo Video Script (about 2 minutes)

**COVID-19 Data Analysis and Visualisation | Yash Verma | 2300320130290**

Record your screen with OBS, the Windows Game Bar (Win + G) or Loom. Keep each section to about the time shown.

---

**0:00 – 0:15 | Introduction** *(show the README on GitHub)*
> "Hello, I am Yash Verma from ABES Engineering College. This is my HCLTech Career Shaper project, number 48: COVID-19 Data Analysis and Visualisation. My mentor is Dipali Kedar Patki."

**0:15 – 0:35 | The data problem** *(open the notebook at Section 2, the audit table)*
> "First I audited the dataset supplied with the brief. Every country had five different populations and continents, and vaccinated was higher than population in 68 percent of rows. So, as the brief's prompt suggests, I used the real Our World in Data COVID-19 dataset and cleaned it into the same eight columns: 391,716 rows across 234 countries."

**0:35 – 0:50 | Cleaning** *(show `src/prepare_data.py` and `data/anomalies.csv`)*
> "The cleaning script removes regional totals, fixes data types and fills vaccination values. It flags five kinds of quality problems instead of deleting them, for example China's backlog of 40 million cases reported in a single week."

**0:50 – 1:25 | Key charts** *(scroll through the notebook: weekly cases, CFR trend, top 15, vaccination)*
> "Worldwide, 776 million cases and 7 million deaths were reported. Deaths peaked in January 2021, while cases peaked with Omicron in January 2022. The case fatality rate fell from 2.4 percent in 2020 to 0.3 percent in 2022. Per million people, Peru and Eastern Europe were hit hardest. Vaccination reached 86 percent in South America but only 39 percent in Africa."

**1:25 – 1:50 | Dashboard** *(open `dashboard/covid_dashboard.html`)*
> "This is the interactive Plotly dashboard. I can pick any country, for example India, to see its Delta wave in May 2021; switch to deaths; change the map to vaccination; and rank the top 15 countries by continent. It works offline."

**1:50 – 2:00 | Close**
> "All figures are officially reported numbers, cited from Our World in Data and the WHO. The code, data, report and dashboard are on my GitHub. Thank you."
