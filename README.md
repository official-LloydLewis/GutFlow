---

# 🥗 Digestive Simulation

> An interactive Rich-powered simulator of human digestion, metabolism, and the gut microbiome.

---

## 📖 Description

**Digestive Simulation** is a Python program that models how food is processed through the human digestive system — from chewing to absorption and waste elimination.
It combines **organ physiology, hormone regulation, microbiome activity, and environmental/health factors** into a dynamic, step-by-step simulation with a real-time terminal UI.

This project is primarily educational: it’s designed to **visualize complex biological processes** and show how digestion is influenced by different factors.

---

## ⚙️ Mechanism Overview

The simulation tracks:

* **Organs**: Mouth, stomach, intestines, etc. Each has its own role and timing.
* **Hormones**: Ghrelin, gastrin, insulin, leptin, and parasympathetic stimulation.
* **Microbiome**: Good vs. bad bacteria, fiber effects, and antibiotic influences.
* **Energy metabolism**: Food nutrients convert to usable energy over time.
* **Environmental factors**: Stress and body temperature alter digestion speed.
* **Health conditions**: Obesity, malabsorption, GERD, and diabetes affect the process.

---

## ✨ Features

* Modular **organ-based design** with clear responsibilities.
* **Hormone regulation system** that changes dynamically with each stage.
* **Microbiome simulation** with bacteria balance and nutrient effects.
* **Interactive Rich UI** with:

  * Live-updating panel (instead of spamming new prints).
  * Progress bar and spinner per stage.
  * Status indicators for hormones, environment, and conditions.
* **User controls**:

  * ⏸ Pause / Resume
  * ⏭ Skip to next stage
  * ⚡ Toggle health conditions (e.g. diabetes, GERD)
  * 🔄 Adjust stress or body temperature
* **Fallback non-Rich mode** if the terminal doesn’t support Rich.

---

## 🚀 Installation

Clone the repository and install requirements:

```bash
git clone https://github.com/YOUR_USERNAME/digestive-simulation.git
cd digestive-simulation
pip install -r requirements.txt
```

Dependencies:

* Python 3.9+
* [rich](https://github.com/Textualize/rich)

---

## ▶️ Usage

Run the program with:

```bash
python GutFlow.py
```

During simulation, you can interact with the program using keyboard controls.

---

## 📊 Example Output

The terminal shows a single **live-updating panel** with:

* Current organ stage + progress bar
* Active hormones and their levels
* Microbiome balance (good vs. bad bacteria)
* Environmental conditions (stress, temperature)
* Health conditions status

*(screenshot placeholder here if you want to add one later)*

---

## 📜 License

This project is licensed under the **MIT License**.
See the [LICENSE](LICENSE) file for details.

---
## ❗ Warning

This project is not yet complete and is old. If you see a bug, you can report it.

---
## 📬 Contact

If you have new ideas, suggestions, or want to get in touch:

* **Email**: [lloydlewizzz@gmail.com](mailto:lloydlewizzz@gmail.com)
* **Discord**: `lloydlewizzz`

---
