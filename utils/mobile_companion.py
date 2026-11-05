# utils/mobile_companion.py
# O!kie Grocery - Mobile Inventory Companion Server & Scanner Engine

from __future__ import annotations
import socket
import uuid
import threading
import io
import time
from datetime import datetime, date
from werkzeug.serving import make_server
from flask import Flask, render_template_string, request, jsonify, session

import qrcode
from PIL import Image, ImageTk
from db.connection import get_connection

# Global active companion session instance
_COMPANION_SERVER = None
_DESKTOP_NOTIFY_CALLBACK = None


def get_local_ip() -> str:
    """Discover local LAN IP address of the host machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ── Full HTML/CSS/JS Mobile Web App Template ──────────────────────────────────
MOBILE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>O!kie Grocery — Mobile Inventory Companion</title>
    <style>
        :root {
            --brand-red: #c8102e;
            --brand-red-dark: #a50b23;
            --brand-amber: #d97706;
            --brand-yellow: #facc15;
            --bg-main: #f8fafc;
            --card-bg: #ffffff;
            --text-dark: #0f172a;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --radius-md: 12px;
            --radius-sm: 8px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            background-color: var(--bg-main);
            color: var(--text-dark);
            padding-bottom: 80px;
        }

        header {
            background-color: var(--brand-red);
            color: #ffffff;
            padding: 16px;
            text-align: center;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }

        header h1 {
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        header p {
            font-size: 0.75rem;
            color: #fef08a;
            margin-top: 2px;
            font-weight: 600;
        }

        .container {
            padding: 16px;
            max-width: 500px;
            margin: 0 auto;
        }

        /* Nav Tabs */
        .tab-bar {
            display: flex;
            background: #ffffff;
            border-radius: var(--radius-md);
            padding: 4px;
            margin-bottom: 16px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
            border: 1px solid var(--border-color);
        }

        .tab-btn {
            flex: 1;
            padding: 10px 4px;
            border: none;
            background: transparent;
            font-size: 0.82rem;
            font-weight: 700;
            color: var(--text-muted);
            border-radius: var(--radius-sm);
            cursor: pointer;
            transition: all 0.2s;
            text-align: center;
        }

        .tab-btn.active {
            background: var(--brand-amber);
            color: #ffffff;
        }

        /* Card Elements */
        .card {
            background: var(--card-bg);
            border-radius: var(--radius-md);
            padding: 16px;
            border: 1px solid var(--border-color);
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            width: 100%;
            box-sizing: border-box;
            overflow: hidden;
        }

        .card-title {
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 12px;
            color: var(--text-dark);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* Form Inputs & iOS Date Picker Fix */
        .form-group {
            margin-bottom: 14px;
            width: 100%;
            box-sizing: border-box;
        }

        .form-label {
            display: block;
            font-size: 0.8rem;
            font-weight: 700;
            color: #334155;
            margin-bottom: 4px;
        }

        .form-control {
            width: 100% !important;
            max-width: 100% !important;
            padding: 12px;
            font-size: 0.95rem;
            border: 1px solid var(--border-color);
            border-radius: var(--radius-sm);
            background: #ffffff;
            color: var(--text-dark);
            outline: none;
            box-sizing: border-box !important;
            -webkit-appearance: none;
        }

        input[type="date"].form-control {
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
            min-height: 48px;
            background-color: #ffffff;
            font-family: inherit;
        }

        .form-control:focus {
            border-color: var(--brand-amber);
            box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.15);
        }

        .btn {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: var(--radius-sm);
            font-size: 0.95rem;
            font-weight: 700;
            cursor: pointer;
            transition: background 0.2s;
            text-align: center;
        }

        .btn-primary {
            background: var(--brand-red);
            color: #ffffff;
        }

        .btn-primary:active {
            background: var(--brand-red-dark);
        }

        .btn-amber {
            background: var(--brand-amber);
            color: #ffffff;
        }

        .btn-secondary {
            background: #e2e8f0;
            color: #334155;
        }

        /* Product Inspector Result */
        .product-card {
            background: #ffffff;
            border: 2px solid var(--brand-amber);
            border-radius: var(--radius-md);
            padding: 16px;
            margin-top: 14px;
            width: 100%;
            box-sizing: border-box;
            overflow: hidden;
        }

        .badge {
            display: inline-block;
            padding: 4px 8px;
            font-size: 0.72rem;
            font-weight: 700;
            border-radius: 4px;
            text-transform: uppercase;
        }

        .badge-danger { background: #fee2e2; color: #991b1b; }
        .badge-warning { background: #fef3c7; color: #92400e; }
        .badge-success { background: #dcfce7; color: #166534; }

        .qty-adjuster {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 12px;
        }

        .btn-qty {
            width: 44px;
            height: 44px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-color);
            background: #f1f5f9;
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--text-dark);
        }

        .qty-val {
            flex: 1;
            text-align: center;
            font-size: 1.2rem;
            font-weight: 700;
        }

        /* Toast Alert */
        #toast {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #0f172a;
            color: #ffffff;
            padding: 12px 24px;
            border-radius: 30px;
            font-size: 0.85rem;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            display: none;
            z-index: 1000;
        }

        /* Login Screen */
        .login-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: var(--brand-red);
            color: #ffffff;
            z-index: 2000;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .login-box {
            background: #ffffff;
            color: var(--text-dark);
            border-radius: var(--radius-md);
            padding: 24px;
            width: 100%;
            max-width: 380px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        }

        .hidden { display: none !important; }
    </style>
</head>
<body>

    <!-- Hidden Native Camera Photo Inputs -->
    <input type="file" id="scan-photo-input" accept="image/*" capture="environment" style="display:none;" onchange="handlePhotoUpload(this, 'inspect')">
    <input type="file" id="add-photo-input" accept="image/*" capture="environment" style="display:none;" onchange="handlePhotoUpload(this, 'add')">

    <!-- Manager Auth Screen -->
    <div id="login-modal" class="login-overlay {% if is_logged_in %}hidden{% endif %}">
        <div class="login-box">
            <h2 style="color: var(--brand-red); font-size: 1.4rem; font-weight: 800; margin-bottom: 4px;">Manager Sign In</h2>
            <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 18px;">Scan & Edit Mobile Inventory</p>
            
            <div class="form-group">
                <label class="form-label">Manager User ID / Username</label>
                <input type="text" id="login-user" class="form-control" placeholder="Enter Manager ID">
            </div>

            <div class="form-group">
                <label class="form-label">Password</label>
                <input type="password" id="login-pass" class="form-control" placeholder="Enter Password">
            </div>

            <button onclick="attemptLogin()" class="btn btn-primary">AUTHENTICATE PHONE</button>
        </div>
    </div>

    <!-- Main Mobile Header -->
    <header>
        <h1>O!kie Grocery</h1>
        <p>MOBILE INVENTORY COMPANION</p>
    </header>

    <div class="container">
        <!-- Navigation Tabs -->
        <div class="tab-bar">
            <button class="tab-btn active" onclick="switchTab('tab-scan')">SCAN & INSPECT</button>
            <button class="tab-btn" onclick="switchTab('tab-add')">ADD PRODUCT</button>
            <button class="tab-btn" onclick="switchTab('tab-search')">SEARCH</button>
        </div>

        <!-- TAB 1: SCAN & INSPECT -->
        <div id="tab-scan">
            <div class="card">
                <div class="card-title">Barcode Camera Scanner</div>
                
                <button onclick="document.getElementById('scan-photo-input').click()" class="btn btn-amber" style="padding: 16px; font-size: 1.05rem; margin-bottom: 12px; display: flex; align-items: center; justify-content: center; gap: 8px;">
                    <span>SNAP BARCODE PHOTO</span>
                </button>

                <p style="font-size: 0.78rem; color: var(--text-muted); text-align: center; margin-bottom: 12px;">
                    Tap button above to open iPhone camera, snap a picture of the barcode, and auto-load item.
                </p>

                <div style="display: flex; gap: 8px;">
                    <input type="text" id="manual-barcode" class="form-control" placeholder="Or enter barcode manually...">
                    <button onclick="lookupManualBarcode()" class="btn btn-primary" style="width: 100px;">LOOKUP</button>
                </div>
            </div>

            <!-- Scanned Product Card -->
            <div id="product-result" class="product-card hidden">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <h3 id="res-name" style="font-size: 1.1rem; font-weight: 700; color: var(--text-dark);">Product Name</h3>
                        <p id="res-barcode" style="font-size: 0.8rem; color: var(--text-muted); font-family: monospace;">SKU: 000000</p>
                    </div>
                    <span id="res-status-badge" class="badge badge-success">IN STOCK</span>
                </div>

                <div style="margin-top: 12px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem;">
                    <div style="background: #f8fafc; padding: 8px; border-radius: 6px;">
                        <span style="color: var(--text-muted); font-size: 0.75rem;">Retail Price:</span>
                        <strong id="res-price" style="display: block; font-size: 1rem; color: var(--brand-red);">PHP 0.00</strong>
                    </div>
                    <div style="background: #f8fafc; padding: 8px; border-radius: 6px;">
                        <span style="color: var(--text-muted); font-size: 0.75rem;">Category:</span>
                        <strong id="res-category" style="display: block; font-size: 0.85rem;">General</strong>
                    </div>
                </div>

                <!-- Stock Quantity Adjuster -->
                <div class="form-group" style="margin-top: 14px;">
                    <label class="form-label">Adjust Stock Quantity</label>
                    <div class="qty-adjuster">
                        <button onclick="adjustQty(-1)" class="btn-qty">-</button>
                        <input type="number" id="res-qty" class="form-control qty-val" value="0" min="0">
                        <button onclick="adjustQty(1)" class="btn-qty">+</button>
                    </div>
                </div>

                <!-- Expiration Date Editor -->
                <div class="form-group">
                    <label class="form-label">Expiration Date</label>
                    <input type="date" id="res-expiry" class="form-control">
                </div>

                <button onclick="saveStockChanges()" class="btn btn-primary" style="margin-top: 8px;">SAVE CHANGES TO LAPTOP</button>
            </div>
        </div>

        <!-- TAB 2: ADD PRODUCT -->
        <div id="tab-add" class="hidden">
            <div class="card">
                <div class="card-title">Add New Product</div>

                <div class="form-group">
                    <label class="form-label">Barcode / SKU</label>
                    <div style="display: flex; gap: 8px;">
                        <input type="text" id="add-barcode" class="form-control" placeholder="Scan or enter barcode">
                        <button onclick="document.getElementById('add-photo-input').click()" class="btn btn-amber" style="width: 120px; font-size: 0.78rem;">SCAN PHOTO</button>
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">Product Name *</label>
                    <input type="text" id="add-name" class="form-control" placeholder="Item full description">
                </div>

                <div class="form-group">
                    <label class="form-label">Category *</label>
                    <select id="add-category" class="form-control">
                        <option value="General">General</option>
                        <option value="Beverages">Beverages</option>
                        <option value="Alcohol & Beverages">Alcohol & Beverages</option>
                        <option value="Snacks">Snacks</option>
                        <option value="Dry Goods">Dry Goods</option>
                        <option value="Frozen">Frozen</option>
                        <option value="Personal Care">Personal Care</option>
                    </select>
                </div>

                <!-- Cost Price & Profit Markup (Desktop Auto-Calc Matching) -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <div class="form-group">
                        <label class="form-label">Cost Price (Wholesale)</label>
                        <input type="number" step="0.01" id="add-cost" class="form-control" placeholder="0.00" oninput="autoCalcPrice()">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Profit Markup (%)</label>
                        <input type="number" step="0.01" id="add-markup" class="form-control" value="20.00" oninput="autoCalcPrice()">
                    </div>
                </div>

                <!-- Auto Calculated Final Retail Selling Price -->
                <div class="form-group">
                    <label class="form-label" style="color: var(--brand-red);">Final Retail Selling Price (PHP, 12% VAT Inc.) *</label>
                    <input type="number" step="0.01" id="add-price" class="form-control" placeholder="0.00" style="font-weight: 700; color: var(--brand-red);">
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <div class="form-group">
                        <label class="form-label">Initial Stock *</label>
                        <input type="number" id="add-stock" class="form-control" value="10">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Min Alert Level</label>
                        <input type="number" id="add-min-stock" class="form-control" value="5">
                    </div>
                </div>

                <!-- Expiration Date Box -->
                <div class="form-group">
                    <label class="form-label">Expiration Date (Optional)</label>
                    <input type="date" id="add-expiry" class="form-control">
                </div>

                <!-- Basic Commodity PWD Checkbox -->
                <div class="form-group" style="display: flex; align-items: center; gap: 8px; background: #f8fafc; padding: 10px; border-radius: 6px;">
                    <input type="checkbox" id="add-commodity" onchange="autoCalcPrice()" style="width: 20px; height: 20px;">
                    <label for="add-commodity" class="form-label" style="margin: 0; cursor: pointer; color: #2563eb;">Basic Commodity (Eligible for 5% PWD / Senior Discount)</label>
                </div>

                <button onclick="submitNewProduct()" class="btn btn-primary" style="margin-top: 10px;">SAVE PRODUCT TO SYSTEM</button>
            </div>
        </div>

        <!-- TAB 3: SEARCH -->
        <div id="tab-search" class="hidden">
            <div class="card">
                <div class="card-title">Search Store Inventory</div>
                <div class="form-group">
                    <input type="text" id="search-query" class="form-control" placeholder="Search product name or SKU..." oninput="doSearch()">
                </div>

                <div id="search-results-list" style="display: flex; flex-direction: column; gap: 8px;">
                    <!-- Dynamically populated -->
                </div>
            </div>
        </div>

    </div>

    <!-- Toast Notification -->
    <div id="toast">Changes saved to Laptop POS!</div>

    <script>
        let currentScannedProduct = null;

        function showToast(msg) {
            const t = document.getElementById('toast');
            t.innerText = msg;
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, 2800);
        }

        function switchTab(tabId) {
            ['tab-scan', 'tab-add', 'tab-search'].forEach(id => {
                document.getElementById(id).classList.add('hidden');
            });
            document.getElementById(tabId).classList.remove('hidden');

            const btns = document.querySelectorAll('.tab-btn');
            btns.forEach(b => b.classList.remove('active'));
            if(tabId === 'tab-scan') btns[0].classList.add('active');
            if(tabId === 'tab-add') {
                btns[1].classList.add('active');
                loadCategories();
            }
            if(tabId === 'tab-search') {
                btns[2].classList.add('active');
                doSearch();
            }
        }

        function autoCalcPrice() {
            const cost = parseFloat(document.getElementById('add-cost').value) || 0;
            const markup = parseFloat(document.getElementById('add-markup').value) || 20;
            const isBasicCommodity = document.getElementById('add-commodity').checked;

            const vatMultiplier = isBasicCommodity ? 1.0 : 1.12;
            const priceNoVat = cost * (1.0 + (markup / 100.0));
            const finalPrice = priceNoVat * vatMultiplier;

            document.getElementById('add-price').value = finalPrice > 0 ? finalPrice.toFixed(2) : '0.00';
        }

        async function attemptLogin() {
            const user = document.getElementById('login-user').value.trim();
            const pass = document.getElementById('login-pass').value.trim();
            if(!user || !pass) {
                alert('Please enter Manager Username and Password.');
                return;
            }

            const res = await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: user, password: pass})
            });
            const data = await res.json();
            if(data.success) {
                document.getElementById('login-modal').classList.add('hidden');
                showToast('Manager Authenticated!');
            } else {
                alert(data.message || 'Invalid Manager credentials.');
            }
        }

        async function handlePhotoUpload(inputEl, targetMode) {
            if(!inputEl.files || !inputEl.files[0]) return;
            showToast('Reading barcode photo...');
            
            const formData = new FormData();
            formData.append('photo', inputEl.files[0]);

            try {
                const res = await fetch('/api/scan_photo', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if(data.success && data.barcode) {
                    showToast('Barcode Found: ' + data.barcode);
                    if(targetMode === 'inspect') {
                        lookupBarcode(data.barcode);
                    } else {
                        document.getElementById('add-barcode').value = data.barcode;
                    }
                } else {
                    alert(data.message || 'Could not decode barcode from photo. Please take a clearer picture.');
                }
            } catch(err) {
                alert('Error processing photo: ' + err);
            }
            inputEl.value = '';
        }

        function lookupManualBarcode() {
            const code = document.getElementById('manual-barcode').value.trim();
            if(code) lookupBarcode(code);
        }

        async function lookupBarcode(barcode) {
            const res = await fetch('/api/product/' + encodeURIComponent(barcode));
            const data = await res.json();
            if(data.success && data.product) {
                renderProductCard(data.product);
            } else {
                alert('Product not found: ' + barcode);
            }
        }

        function renderProductCard(p) {
            currentScannedProduct = p;
            document.getElementById('res-name').innerText = p.item_name || p.product_name;
            document.getElementById('res-barcode').innerText = 'SKU / Barcode: ' + p.barcode;
            document.getElementById('res-price').innerText = 'PHP ' + parseFloat(p.unit_price).toFixed(2);
            document.getElementById('res-category').innerText = p.category || p.category_name || 'General';
            document.getElementById('res-qty').value = p.stock_qty;
            document.getElementById('res-expiry').value = p.expiration_date || p.expiry_date || '';

            const badge = document.getElementById('res-status-badge');
            if(p.stock_qty <= 0) {
                badge.innerText = 'OUT OF STOCK';
                badge.className = 'badge badge-danger';
            } else if(p.stock_qty <= (p.reorder_level || 5)) {
                badge.innerText = 'LOW STOCK';
                badge.className = 'badge badge-warning';
            } else {
                badge.innerText = 'IN STOCK';
                badge.className = 'badge badge-success';
            }

            document.getElementById('product-result').classList.remove('hidden');
        }

        function adjustQty(delta) {
            const q = document.getElementById('res-qty');
            let val = parseInt(q.value) || 0;
            val = Math.max(0, val + delta);
            q.value = val;
        }

        async function saveStockChanges() {
            if(!currentScannedProduct) return;
            const newQty = parseInt(document.getElementById('res-qty').value) || 0;
            const newExpiry = document.getElementById('res-expiry').value;

            const res = await fetch('/api/update_stock', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    product_id: currentScannedProduct.item_id || currentScannedProduct.product_id,
                    new_qty: newQty,
                    expiration_date: newExpiry
                })
            });
            const data = await res.json();
            if(data.success) {
                showToast('Updated ' + (currentScannedProduct.item_name || currentScannedProduct.product_name) + '!');
                currentScannedProduct.stock_qty = newQty;
                renderProductCard(currentScannedProduct);
            } else {
                alert(data.message || 'Error updating product.');
            }
        }

        async function loadCategories() {
            const sel = document.getElementById('add-category');
            const res = await fetch('/api/categories');
            const data = await res.json();
            if(data.success && data.categories && data.categories.length > 0) {
                sel.innerHTML = '';
                data.categories.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.category_name || c;
                    opt.innerText = c.category_name || c;
                    sel.appendChild(opt);
                });
            }
        }

        async function submitNewProduct() {
            const barcode = document.getElementById('add-barcode').value.trim();
            const name = document.getElementById('add-name').value.trim();
            const category = document.getElementById('add-category').value;
            const price = parseFloat(document.getElementById('add-price').value) || 0;
            const cost = parseFloat(document.getElementById('add-cost').value) || 0;
            const markup = parseFloat(document.getElementById('add-markup').value) || 20.0;
            const stock = parseInt(document.getElementById('add-stock').value) || 0;
            const minStock = parseInt(document.getElementById('add-min-stock').value) || 5;
            const expiry = document.getElementById('add-expiry').value;
            const isCommodity = document.getElementById('add-commodity').checked ? 1 : 0;

            if(!name || price <= 0) {
                alert('Please enter Product Name and Selling Price.');
                return;
            }

            const res = await fetch('/api/add_product', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    barcode: barcode,
                    product_name: name,
                    category: category,
                    unit_price: price,
                    cost_price: cost,
                    markup_percent: markup,
                    stock_qty: stock,
                    reorder_level: minStock,
                    expiration_date: expiry,
                    is_basic_commodity: isCommodity
                })
            });
            const data = await res.json();
            if(data.success) {
                showToast('Product Created on Laptop POS!');
                document.getElementById('add-barcode').value = '';
                document.getElementById('add-name').value = '';
                document.getElementById('add-cost').value = '';
                document.getElementById('add-price').value = '';
                document.getElementById('add-stock').value = '10';
            } else {
                alert(data.message || 'Failed to create product.');
            }
        }

        async function doSearch() {
            const q = document.getElementById('search-query').value.trim();
            const res = await fetch('/api/search?q=' + encodeURIComponent(q));
            const data = await res.json();
            const container = document.getElementById('search-results-list');
            container.innerHTML = '';

            if(data.success && data.products && data.products.length > 0) {
                data.products.forEach(p => {
                    const div = document.createElement('div');
                    div.className = 'card';
                    div.style.padding = '12px';
                    div.style.marginBottom = '8px';
                    div.style.cursor = 'pointer';
                    div.onclick = () => {
                        switchTab('tab-scan');
                        renderProductCard(p);
                    };
                    div.innerHTML = `
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <strong style="font-size:0.95rem;">${p.item_name || p.product_name}</strong>
                            <strong style="color:var(--brand-red); font-size:1rem;">PHP ${parseFloat(p.unit_price).toFixed(2)}</strong>
                        </div>
                        <div style="font-size:0.8rem; color:var(--text-muted); margin-top:4px;">
                            SKU: ${p.barcode || 'N/A'} | Category: ${p.category || 'General'} | Stock: <strong>${p.stock_qty}</strong>
                        </div>
                    `;
                    container.appendChild(div);
                });
            } else {
                container.innerHTML = '<p style="text-align:center; color:var(--text-muted); padding:20px; font-size:0.85rem;">No products found.</p>';
            }
        }
    </script>
</body>
</html>
"""


class CompanionServerThread:
    """Manages background Flask web server lifecycle & token verification."""

    def __init__(self, host: str, port: int = 5050, notify_callback=None):
        self.host = host
        self.port = port
        self.token = uuid.uuid4().hex
        self.notify_callback = notify_callback
        self.app = Flask("MobileCompanion")
        self.app.secret_key = self.token
        self.server = None
        self.thread = None
        self._register_routes()

    def _register_routes(self):
        @self.app.route("/")
        def index():
            req_token = request.args.get("token")
            if req_token and req_token != self.token:
                return "Invalid or Expired Mobile Session Token.", 403

            is_logged_in = session.get("manager_authenticated", False)
            return render_template_string(MOBILE_HTML_TEMPLATE, is_logged_in=is_logged_in)

        @self.app.route("/api/login", methods=["POST"])
        def api_login():
            data = request.get_json() or {}
            user_input = data.get("username", "").strip()
            pass_input = data.get("password", "").strip()

            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT * FROM users
                    WHERE (username = %s OR user_code = %s) AND password = %s AND role = 'manager' AND is_active = 1
                """, (user_input, user_input, pass_input))
                user = cursor.fetchone()
                conn.close()

                if user:
                    session["manager_authenticated"] = True
                    session["user_name"] = user.get("full_name")
                    return jsonify({"success": True, "full_name": user.get("full_name")})
                else:
                    return jsonify({"success": False, "message": "Invalid Manager credentials."}), 401
            except Exception as e:
                return jsonify({"success": False, "message": str(e)}), 500

        @self.app.route("/api/categories")
        def api_categories():
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != '' ORDER BY category ASC")
                rows = cursor.fetchall()
                conn.close()
                cats = [r["category"] for r in rows] if rows else ["General", "Beverages", "Alcohol & Beverages", "Snacks", "Dry Goods", "Frozen", "Personal Care"]
                return jsonify({"success": True, "categories": cats})
            except Exception as e:
                return jsonify({"success": False, "message": str(e)}), 500

        @self.app.route("/api/product/<barcode>")
        def api_get_product(barcode):
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT * FROM products
                    WHERE barcode = %s OR item_id = %s
                """, (barcode, barcode))
                prod = cursor.fetchone()
                conn.close()

                if prod:
                    prod["product_id"] = prod["item_id"]
                    prod["product_name"] = prod["item_name"]
                    prod["category_name"] = prod.get("category", "General")
                    if isinstance(prod.get("expiry_date"), (datetime, date)):
                        prod["expiration_date"] = prod["expiry_date"].strftime("%Y-%m-%d")
                    return jsonify({"success": True, "product": prod})
                else:
                    return jsonify({"success": False, "message": "Product not found"}), 404
            except Exception as e:
                return jsonify({"success": False, "message": str(e)}), 500

        @self.app.route("/api/scan_photo", methods=["POST"])
        def api_scan_photo():
            if "photo" not in request.files:
                return jsonify({"success": False, "message": "No photo file provided"}), 400

            file = request.files["photo"]
            try:
                import zxingcpp
                from PIL import Image
                img_bytes = file.read()
                pil_img = Image.open(io.BytesIO(img_bytes))
                results = zxingcpp.read_barcodes(pil_img)
                if results:
                    barcode = results[0].text
                    return jsonify({"success": True, "barcode": barcode})
                else:
                    return jsonify({"success": False, "message": "Could not read barcode from photo. Please ensure barcode is clear and retry."})
            except Exception as e:
                return jsonify({"success": False, "message": f"Barcode scan error: {e}"}), 500

        @self.app.route("/api/update_stock", methods=["POST"])
        def api_update_stock():
            if not session.get("manager_authenticated"):
                return jsonify({"success": False, "message": "Unauthorized"}), 401

            data = request.get_json() or {}
            item_id = data.get("product_id") or data.get("item_id")
            new_qty = data.get("new_qty", 0)
            exp_date = data.get("expiration_date") or None

            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)

                cursor.execute("SELECT stock_qty, item_name FROM products WHERE item_id = %s", (item_id,))
                old_p = cursor.fetchone()
                if not old_p:
                    conn.close()
                    return jsonify({"success": False, "message": "Product not found"}), 404

                old_qty = old_p["stock_qty"]
                qty_diff = new_qty - old_qty

                cursor.execute("""
                    UPDATE products
                    SET stock_qty = %s, expiry_date = %s
                    WHERE item_id = %s
                """, (new_qty, exp_date, item_id))

                if qty_diff != 0:
                    try:
                        m_type = "restock" if qty_diff > 0 else "adjustment"
                        user_name = session.get("user_name", "Mobile Admin")
                        note = f"Mobile Companion Stock Update by {user_name} (Qty: {old_qty} -> {new_qty})"
                        cursor.execute("""
                            INSERT INTO inventory_movements (item_id, movement_type, quantity, notes, moved_at)
                            VALUES (%s, %s, %s, %s, NOW())
                        """, (item_id, m_type, abs(qty_diff), note))
                    except Exception as err:
                        print(f"Error recording mobile inventory movement: {err}")

                conn.commit()
                conn.close()

                if self.notify_callback:
                    self.notify_callback()

                return jsonify({"success": True})
            except Exception as e:
                return jsonify({"success": False, "message": str(e)}), 500

        @self.app.route("/api/add_product", methods=["POST"])
        def api_add_product():
            if not session.get("manager_authenticated"):
                return jsonify({"success": False, "message": "Unauthorized"}), 401

            data = request.get_json() or {}
            barcode = data.get("barcode", "").strip()
            item_name = data.get("product_name", "").strip() or data.get("item_name", "").strip()
            category = data.get("category", "").strip() or "General"
            price = data.get("unit_price", 0.0)
            cost = data.get("cost_price", 0.0)
            markup = data.get("markup_percent", 20.0)
            stock = data.get("stock_qty", 0)
            reorder = data.get("reorder_level", 5)
            exp_date = data.get("expiration_date") or None
            is_commodity = 1 if data.get("is_basic_commodity") else 0

            if not barcode:
                barcode = f"OK-{int(time.time())}"

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO products 
                    (barcode, item_name, category, unit_price, cost_price, markup_percent, stock_qty, reorder_level, expiry_date, is_basic_commodity, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                """, (barcode, item_name, category, price, cost, markup, stock, reorder, exp_date, is_commodity))
                new_id = cursor.lastrowid

                if stock > 0:
                    try:
                        user_name = session.get("user_name", "Mobile Admin")
                        note = f"Initial Stock via Mobile Companion by {user_name} (Qty: {stock})"
                        cursor.execute("""
                            INSERT INTO inventory_movements (item_id, movement_type, quantity, notes, moved_at)
                            VALUES (%s, 'restock', %s, %s, NOW())
                        """, (new_id, stock, note))
                    except Exception as err:
                        print(f"Error recording mobile initial stock movement: {err}")

                conn.commit()
                conn.close()

                if self.notify_callback:
                    self.notify_callback()

                return jsonify({"success": True, "product_id": new_id})
            except Exception as e:
                return jsonify({"success": False, "message": str(e)}), 500

        @self.app.route("/api/search")
        def api_search():
            q = request.args.get("q", "").strip()
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                if q:
                    cursor.execute("""
                        SELECT * FROM products
                        WHERE (item_name LIKE %s OR barcode LIKE %s) AND is_active = 1
                        ORDER BY item_name ASC LIMIT 30
                    """, (f"%{q}%", f"%{q}%"))
                else:
                    cursor.execute("""
                        SELECT * FROM products
                        WHERE is_active = 1
                        ORDER BY item_name ASC LIMIT 30
                    """)
                prods = cursor.fetchall()
                conn.close()

                for p in prods:
                    p["product_id"] = p["item_id"]
                    p["product_name"] = p["item_name"]
                    p["category_name"] = p.get("category", "General")
                    if isinstance(p.get("expiry_date"), (datetime, date)):
                        p["expiration_date"] = p["expiry_date"].strftime("%Y-%m-%d")

                return jsonify({"success": True, "products": prods})
            except Exception as e:
                return jsonify({"success": False, "message": str(e)}), 500

    def start(self):
        """Launches Werkzeug server in a background daemon thread."""
        self.server = make_server(self.host, self.port, self.app)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops background web server cleanly."""
        if self.server:
            self.server.shutdown()
            self.server = None


def generate_qr_code_image(url: str) -> ImageTk.PhotoImage:
    """Generates high-contrast QR Code Image for Tkinter rendering."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=5,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")

    buf = io.BytesIO()
    img.get_image().save(buf, format="PNG")
    buf.seek(0)
    pil_img = Image.open(buf)
    return ImageTk.PhotoImage(pil_img)


def start_mobile_companion_session(notify_callback=None) -> tuple[str, ImageTk.PhotoImage]:
    """
    Initializes server on active LAN IP and returns (server_url, qr_tk_image).
    Invalidates any existing active session.
    """
    global _COMPANION_SERVER, _DESKTOP_NOTIFY_CALLBACK
    if _COMPANION_SERVER:
        _COMPANION_SERVER.stop()

    _DESKTOP_NOTIFY_CALLBACK = notify_callback
    lan_ip = get_local_ip()
    port = 5050

    _COMPANION_SERVER = CompanionServerThread(host="0.0.0.0", port=port, notify_callback=notify_callback)
    _COMPANION_SERVER.start()

    full_url = f"http://{lan_ip}:{port}/?token={_COMPANION_SERVER.token}"
    qr_tk = generate_qr_code_image(full_url)
    return full_url, qr_tk


def stop_mobile_companion_session():
    """Stops active companion server and invalidates token."""
    global _COMPANION_SERVER
    if _COMPANION_SERVER:
        _COMPANION_SERVER.stop()
        _COMPANION_SERVER = None
