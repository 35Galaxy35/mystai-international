// firestore.js
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getFirestore, collection, addDoc, getDocs, query, where } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { getAuth, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

// Firebase yapılandırması (senin projenle aynı olmalı)
const firebaseConfig = {
  apiKey: "AIzaSyDyiD7GAfOjMbtm-S6pO6XCSRXJclffPL0",
  authDomain: "mystai-6cca2.firebaseapp.com",
  projectId: "mystai-6cca2",
  storageBucket: "mystai-6cca2.appspot.com",
  messagingSenderId: "624127781219",
  appId: "1:624127781219:web:a580ac6e80ccc26e694b56"
};

// Firebase başlat
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const auth = getAuth(app);

// Kullanıcı giriş yaptıysa onun geçmişini al
export async function getUserFortunes() {
  const user = auth.currentUser;
  if (!user) return [];
  const fortunesRef = collection(db, "fortunes");
  const q = query(fortunesRef, where("userId", "==", user.uid));
  const snapshot = await getDocs(q);
  return snapshot.docs.map(doc => doc.data());
}

// Yeni fal kaydı ekle
export async function addFortune(type, result) {
  const user = auth.currentUser;
  if (!user) {
    console.warn("Giriş yapılmadan fal kaydedilemez.");
    return;
  }

  try {
    await addDoc(collection(db, "fortunes"), {
      userId: user.uid,
      type: type,
      result: result,
      timestamp: new Date()
    });
    console.log("Yeni fal kaydı eklendi:", type);
  } catch (e) {
    console.error("Fal kaydı eklenemedi:", e);
  }
}
