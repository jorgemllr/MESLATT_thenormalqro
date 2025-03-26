# Custom AI Chatbot for Business Integration – MIT Portfolio Version

This repository was originally private, as it contains the architecture and functionality behind a chatbot system I developed for businesses—primarily nightclubs—as part of my entrepreneurial work. However, I’ve adapted and sanitized the code for academic review, and I'm sharing it here as part of my portfolio for my MIT transfer application.

## 🧠 Overview

This is a customizable AI chatbot designed for businesses that need to manage client interactions in a dynamic and automated way. The system is built with flexibility in mind: for each business, I adjust the design, branding, and data context to deliver a unique user experience.

The version showcased here has been tailored for MIT, including a dedicated dataset (`data.txt`) that allows the chatbot to answer questions specifically about my portfolio, the codebase, and the purpose of each project.

## ⚙️ Deployment Instructions

1. Clone the repository.
2. Deploy it to [Railway](https://railway.app).
3. Set the required environment variables for:
   - Your [OpenAI API Key](https://platform.openai.com/)
   - A working database (PostgreSQL recommended).

Once deployed, the chatbot will be live and functional based on the contents of `data.txt`.

## 📁 How It Works

- The core of the chatbot is powered by OpenAI’s API and a simple but structured context system based on `data.txt`.
- This file holds the entire context of the chatbot, designed to answer frequently asked questions for each specific business.
- We build `data.txt` by scraping customer messages and using tools like ChatGPT to identify the most common questions and clean them into a concise context.

### Business Customization

For each business, I simply:
- Replace logos and visual styles
- Modify `data.txt` to reflect the business’s FAQ
- Integrate a 3D model (if needed)
- Update the database schema if necessary

This allows rapid deployment of personalized AI chatbots for different clients.

## 🔐 Database and Invitations

The chatbot collects user data through conversation and writes it to a database. When the data is confirmed, the system generates and sends a **personalized invitation**, complete with a unique QR code.

- The QR is generated using a hash function and acts as the invitation ID.
- The structure of the specific database being used for this MIT version can be found in `Key.txt`.
- There is also a background function that replicates the database to a backup version periodically. Currently, this interval is set to every **10,000 hours** to ensure the current MIT-related data remains intact.

In this MIT version:
- The "Pending" button updates to "Confirmed" in the session interface once a submission is validated.
- This state change is also reflected in the database in real time.

## 🤖 Ask the Bot or Contact Me

If you have **any questions about how the chatbot works**, its implementation, or deployment, feel free to **ask the chatbot directly**—it’s designed to assist you.

For anything more specific, I’d be happy to help:  
📧 jorgecf29@hotmail.com

---

Thank you for reviewing this project as part of my MIT transfer application.

– **Jorge Uriel Cabrera Morales**
