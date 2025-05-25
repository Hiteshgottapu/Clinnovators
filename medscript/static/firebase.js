// Import the functions you need from the Firebase SDKs
import { initializeApp } from "https://www.gstatic.com/firebasejs/9.22.1/firebase-app.js";
import { getAuth, onAuthStateChanged, signInWithEmailAndPassword, signOut, updateProfile } from "https://www.gstatic.com/firebasejs/9.22.1/firebase-auth.js";
import { getDatabase, ref as dbRef, set, get, child } from "https://www.gstatic.com/firebasejs/9.22.1/firebase-database.js";

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "{{ FIREBASE_API_KEY }}",
    authDomain: "{{ FIREBASE_AUTH_DOMAIN }}",
    projectId: "{{ FIREBASE_PROJECT_ID }}",
    databaseURL: "{{ FIREBASE_DATABASE_URL }}",
    storageBucket: "{{ FIREBASE_STORAGE_BUCKET }}",
    messagingSenderId: "{{ FIREBASE_MESSAGING_SENDER_ID }}",
    appId: "{{ FIREBASE_APP_ID }}",
    measurementId: "{{ FIREBASE_MEASUREMENT_ID }}"
};

// Initialize Firebase
let app;
let auth;
let database;

try {
    // Initialize Firebase only if not already initialized
    if (!firebase.apps.length) {
        app = firebase.initializeApp(firebaseConfig);
    } else {
        app = firebase.app();
    }
    auth = firebase.auth();
    database = firebase.database();
    console.log("Firebase initialized successfully");
} catch (error) {
    console.error("Error initializing Firebase:", error);
}

// Function to convert File to Base64
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
    });
}

// Function to compress image before upload
async function compressImage(file) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = (e) => {
            const img = new Image();
            img.src = e.target.result;
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const MAX_WIDTH = 800;
                const MAX_HEIGHT = 800;
                let width = img.width;
                let height = img.height;

                if (width > height) {
                    if (width > MAX_WIDTH) {
                        height *= MAX_WIDTH / width;
                        width = MAX_WIDTH;
                    }
                } else {
                    if (height > MAX_HEIGHT) {
                        width *= MAX_HEIGHT / height;
                        height = MAX_HEIGHT;
                    }
                }

                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                
                // Get compressed base64 string
                const compressedBase64 = canvas.toDataURL('image/jpeg', 0.7);
                resolve(compressedBase64);
            };
        };
    });
}

// Function to upload profile photo
export async function uploadProfilePhoto(file) {
    try {
        const user = auth.currentUser;
        if (!user) throw new Error('No user logged in');

        // Validate file
        if (!file || !file.type.startsWith('image/')) {
            throw new Error('Please upload a valid image file');
        }

        // Check file size (max 5MB)
        const maxSize = 5 * 1024 * 1024; // 5MB
        if (file.size > maxSize) {
            throw new Error('Image size should be less than 5MB');
        }

        // Compress and convert image to base64
        const compressedBase64 = await compressImage(file);

        // Save to Firebase Realtime Database
        const userPhotoRef = dbRef(database, `users/${user.uid}/profile`);
        await set(userPhotoRef, {
            photoURL: compressedBase64,
            lastUpdated: new Date().toISOString()
        });

        // Update user profile in Firebase Auth
        await updateProfile(user, {
            photoURL: compressedBase64
        });

        return compressedBase64;
    } catch (error) {
        console.error('Error uploading profile photo:', error);
        throw error;
    }
}

// Function to initialize profile photo
export async function initializeProfilePhoto() {
    try {
        const user = auth.currentUser;
        if (!user) return;

        const userPhotoRef = dbRef(database, `users/${user.uid}/profile`);
        const snapshot = await get(userPhotoRef);
        
        if (snapshot.exists()) {
            const userData = snapshot.val();
            if (userData.photoURL) {
                const profilePhoto = document.getElementById('profilePhoto');
                if (profilePhoto) {
                    profilePhoto.src = userData.photoURL;
                }
            }
        }
    } catch (error) {
        console.error('Error initializing profile photo:', error);
    }
}

// Function to save user profile
export async function saveUserProfile(formData) {
    try {
        const user = auth.currentUser;
        if (!user) {
            console.error('No user logged in');
            window.location.href = '/login';
            return;
        }

        const idToken = await user.getIdToken(true);
        if (!idToken) {
            window.location.href = '/login';
            return;
        }

        // Convert FormData to object
        const formDataObj = {};
        for (let [key, value] of formData.entries()) {
            if (key === 'phone') {
                value = value.trim();
                if (value && !value.startsWith('+')) {
                    value = '+' + value;
                }
            }
            formDataObj[key] = value;
        }

        // Save to Firebase Realtime Database
        const userProfileRef = dbRef(database, `users/${user.uid}/profile`);
        await set(userProfileRef, {
            ...formDataObj,
            lastUpdated: new Date().toISOString()
        });

        return true;
    } catch (error) {
        console.error('Error saving profile:', error);
        return false;
    }
}

// Handle auth state changes
onAuthStateChanged(auth, async (user) => {
    if (user) {
        console.log("User is signed in:", user.email);
        if (window.location.pathname === '/profile') {
            try {
                const userPhotoRef = dbRef(database, `users/${user.uid}/profile`);
                const snapshot = await get(userPhotoRef);
                
                if (snapshot.exists()) {
                    const userData = snapshot.val();
                    // Update form fields with user data
                    Object.keys(userData).forEach(field => {
                        const element = document.getElementById(field);
                        if (element) {
                            if (element.type === 'checkbox') {
                                element.checked = userData[field];
                            } else {
                                element.value = userData[field] || '';
                            }
                        }
                    });
                }
            } catch (error) {
                console.error("Error loading profile:", error);
                // Continue silently on error
            }
        }
    } else {
        // Only redirect if not on auth-related pages
        const currentPath = window.location.pathname;
        if (!currentPath.match(/^\/(login|signup|forgot-password|auth)/)) {
            window.location.href = '/login';
        }
    }
});

// Handle logout
const logoutButton = document.querySelector('a[href="/logout"]');
if (logoutButton) {
    logoutButton.addEventListener('click', async (e) => {
        e.preventDefault();
        try {
            await signOut(auth);
            window.location.href = '/login';
        } catch (error) {
            console.error('Error signing out:', error);
        }
    });
}

// Export the initialized Firebase instances
export { app, auth, database };
