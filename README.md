# UrbanWise

> **A bad-air-day assistant for Indian cities**, built for **Environmental Hacks Track 1 (Air)**.  
> Most AQI apps only tell you *what* the air is like. **UrbanWise** also shows *why* it's bad and *what to do*.

---

## 🚨 The Problem

Every winter, Delhi-NCR and other North Indian cities spend weeks with **"Very Poor"** or **"Severe"** air:
- **Schools** guess whether to hold assembly or PE outdoors.
- **Parents** see an AQI number without knowing what it means for their child.
- **People at higher risk** can't plan around the worst hours.
- **Residents** can't see how stubble burning affects the air they breathe.

---

## 👥 Who It's For

- 🏫 **School administrators**
- 👨‍👩‍👧 **Parents**
- 🫁 **High-risk people** (asthma, heart conditions, the elderly)
- 🌆 **Residents** who want to know where their smoke comes from

---

## ✨ Features

### ⭐ Headline Features

* 🔥 **Smoke Trail**: Traces your city's air back 24–48 hours using wind data, matches the path against NASA satellite fire detections, and animates it on a map: *"Your air likely passed over 212 fires near Sangrur and Bathinda."*
* 📝 **School Circular Generator**: When bad air is forecast, it drafts a notice to parents in **English, Hindi, and Punjabi**. The principal reviews it and shares it on WhatsApp.

### ⚙️ Core Features

* 🌡️ **Today's Air**: Current AQI on the Indian (CPCB) scale, with plain-language advice.
* 📈 **48-Hour Forecast**: Shows the best and worst hours to be outside.
* 🏫 **School Mode**: Go, limit, or cancel decisions for assembly, PE, and dismissal, based on CPCB bands, GRAP stages, and the forecast for each hour.
* 🫁 **Exposure Calculator**: Your dose from time outdoors, activity, and how sensitive you are, shown as a cigarette equivalent.
* 🎙️ **AI Assistant**: Answers voice or text questions using live data.

### 🚀 Stretch Features
* 🪟 **Ventilation Window**: The cleanest hours today to open windows.
* 🌐 **Hindi/English Toggle**: Multilingual interface switcher.
* 🔔 **Saved Places with Alerts**: Save custom locations for automated notifications.

---

## 🛠️ Tech and AWS

- **Frontend**: Vue 3, Vite, Leaflet, Chart.js
- **Backend**: Flask, with Gemini for the AI parts
- **Data**: WAQI, Open-Meteo (air-quality forecast and winds), NASA FIRMS
- **AWS Hosting**: S3 serves the frontend, CloudFront provides one HTTPS domain, Lambda runs the API, and DynamoDB optionally stores saved places.

---

## 🎯 Track 1 Coverage

It covers all **five Track 1 topics**:

| Track 1 Topic | UrbanWise Feature |
| :--- | :--- |
| **AQI Monitoring** | Today's Air and the forecast |
| **Exposure** | Exposure calculator |
| **Stubble Burning** | Smoke Trail |
| **School Safety** | School Mode and the circular generator |
| **Indoor Air** | Ventilation Window (stretch feature) |

---
