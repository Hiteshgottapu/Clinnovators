import React, { useState } from 'react';

function AIConsultant() {
  const [formData, setFormData] = useState({
    name: '',
    age: '',
    location: '',
    symptoms: '',
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      const data = await response.json();
      if (data.error) {
        setError(data.error);
        setResult(null);
      } else {
        setResult(data);
        set
      }
    } catch (error) {
      console.error('Error:', error);
      setError('An error occurred while predicting the disease.');
      setResult(null);
    }
  };

  return (
    <div className="ai-consultant">
      <h2>AI Consultant</h2>
      <p>Enter your details to get a health assessment.</p>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          name="name"
          value={formData.name}
          onChange={handleChange}
          placeholder="Enter your name"
          required
        />
        <input
          type="number"
          name="age"
          value={formData.age}
          onChange={handleChange}
          placeholder="Enter your age"
          required
        />
        <input
          type="text"
          name="location"
          value={formData.location}
          onChange={handleChange}
          placeholder="Enter your location"
          required
        />
        <input
          type="text"
          name="symptoms"
          value={formData.symptoms}
          onChange={handleChange}
          placeholder="Enter your symptoms"
          required
        />
        <button type="submit">Predict</button>
      </form>
      {error && <div className="error">{error}</div>}
      {result && (
        <div className="result">
          <h3>Prediction Result:</h3>
          <p><strong>Name:</strong> {result.name}</p>
          <p><strong>Age:</strong> {result.age}</p>
          <p><strong>Location:</strong> {result.location}</p>
          <p><strong>Symptoms:</strong> {result.symptoms}</p>
          <p><strong>Predicted Disease:</strong> {result.predicted_disease}</p>
          <p><strong>Description:</strong> {result.dis_des}</p>
          <p><strong>Precautions:</strong> {result.my_precautions.join(', ')}</p>
          <p><strong>Medications:</strong> {result.medications.join(', ')}</p>
          <p><strong>Workouts:</strong> {result.workout.join(', ')}</p>
          <p><strong>Diets:</strong> {result.my_diet.join(', ')}</p>
        </div>
      )}
    </div>
  );
}

export default AIConsultant;
