import { createRoot } from "react-dom/client";

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./assets/styles/index.scss";

const root = ReactDOM.createRoot(document.getElementById("root"));
const API_URL = process.env.REACT_APP_API_URL;

root.render(<App tab="home" />);
