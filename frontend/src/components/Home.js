import React from 'react';
import { Link } from 'react-router-dom';

function Home() {
  return (
    <div className="home">
      <div className="hero">
        <h1>Transform Your Medical <br /><span>Prescriptions</span> Digitally</h1>
        <p>Streamline your practice with our advanced prescription digitization system.<br />Save time, reduce errors, and enhance patient care with our innovative solution.</p>
        <div className="buttons">
          <Link to="/login" className="primary-btn">Start digitization <i className="fas fa-sign-in-alt"></i></Link>
          <Link to="/features" className="secondary-btn">Learn More <i className="fas fa-info-circle"></i></Link>
        </div>
      </div>
      <div className="sections-container">
        <div className="section">
          <div className="section-content">
            <h2>Med Script</h2>
            <h4>Scan your Medical Precription to a Digital Healthcare Report</h4>
            <p>MedScript harnesses advanced image processing techniques to extract text from uploaded prescriptions. This innovative feature transforms traditional, often cumbersome paper-based prescriptions into digital data, thereby streamlining the way we manage and review vital medical information. Moreover, the platform's AI-powered medical assistant listens to your inquiries and delivers concise, well-formulated responses, ensuring that every piece of advice is both relevant and empathetic.</p>
            <Link to="/medscript" className="section-btn">Med Script</Link>
          </div>
          <div className="section-image">
            <img src="/static/1.jpg" alt="Section 1 Image" />
          </div>
        </div>
        <div className="section">
          <div className="section-image">
            <img src="/static/2.jpg" alt="Section 2 Image" />
          </div>
          <div className="section-content">
            <h2>Med Search</h2>
            <h4>Smart Medicine Search - Compare Prices & Find the Best Deals!</h4>
            <p>Med Search application scours popular online pharmacies like Truemeds, PharmEasy, and Tata 1mg, presenting users with a clear, consolidated view of pricing options. This price comparison functionality not only ensures cost efficiency but also elevates the decision-making process, making it easier for users to access affordable healthcare.</p>
            <Link to="/medicine_search" className="section-btn">Med Search</Link>
          </div>
        </div>
        <div className="section">
          <div className="section-content">
            <h2>Medibot</h2>
            <h4>24/7 Availability - Your virtual health assistant, always ready</h4>
            <p>The chatbot is a well-integrated component within the larger project. It combines a clean, user-friendly interface with robust back-end logic that preprocesses medical queries, interacts with a state-of-the-art generative language API, and formats the response appropriately. While designed to assist with medical inquiries, it also includes safeguards (like error handling and disclaimers) to manage potential inaccuracies in AI-generated advice.</p>
            <Link to="/chatbot" className="section-btn">Medibot</Link>
          </div>
          <div className="section-image">
            <img src="/static/3.jpg" alt="Section 3 Image" />
          </div>
        </div>
        <div className="section">
          <div className="section-image">
            <img src="/static/4.jpg" alt="Section 4 Image" />
          </div>
          <div className="section-content">
            <h2>AI Consultant</h2>
            <h4>AI Consultant – Your Smart Health Guide</h4>
            <p>Our AI Consultant leverages cutting-edge machine learning to analyze your symptoms and predict potential health conditions with accuracy. Simply enter your symptoms, and our intelligent system will provide a detailed health assessment, complete with medication recommendations, precautionary measures, and lifestyle advice. The platform also supports voice input for seamless interaction and allows you to download a comprehensive health report for future reference. Experience the future of personalized healthcare - where AI meets precision in diagnostics.</p>
            <Link to="/ai_consultant" className="section-btn">AI Consultant</Link>
          </div>
        </div>
      </div>
      <div className="cards-container">
        <div className="card">
          <img src="/static/5.jpg" alt="Card 5 Image" />
          <div className="card-content">
            <h3>Features</h3>
            <p>Our platform offers AI-driven healthcare solutions, including instant disease predictions, an intelligent medical chatbot, real-time medicine price comparisons, and AI-powered prescription digitization. Experience seamless, reliable, and efficient health management.</p>
            <Link to="/features" className="card-btn">Read More</Link>
          </div>
        </div>
        <div className="card">
          <img src="/static/6.jpg" alt="Card 6 Image" />
          <div className="card-content">
            <h3>Developers</h3>
            <p>Our dedicated team of developers combines expertise in AI, machine learning, and healthcare technology to build innovative, user-friendly solutions. Passionate about transforming digital healthcare, we strive to enhance accessibility, efficiency, and reliability for all users.</p>
            <Link to="/developers" className="card-btn">Read More</Link>
          </div>
        </div>
        <div className="card">
          <img src="/static/7.jpg" alt="Card 7 Image" />
          <div className="card-content">
            <h3>Contact Us</h3>
            <p>Need assistance or have inquiries? Our team is always ready to help! Reach out via email or fill our contact form for quick support. We're committed to making your healthcare experience seamless and hassle-free! Reach out today and let’s make healthcare smarter together.</p>
            <Link to="/contact" className="card-btn">Read More</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Home;
