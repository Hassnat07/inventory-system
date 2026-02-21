let items = [];
let selectedIndex = -1;
let invoiceEdited = false; // 🔑 TRACK MANUAL EDIT

// ================= ITEM HANDLING =================
function formatPower(value) {
    value = value.trim();
    if (!value) return "";

    const num = parseFloat(value);
    if (isNaN(num)) return value; // fallback (if user types text)

    if (Number.isInteger(num)) {
        return num.toFixed(1) + "D";   // 10 → 10.0D
    }
    return num + "D";                  // 13.5 → 13.5D
}

function isMobileDevice() {
    return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
}

function addItem() {
    const desc = document.getElementById("desc").value.trim();
    const rawPower = document.getElementById("power").value;
    const power = formatPower(rawPower);
    const qty = parseInt(document.getElementById("qty").value);
    const price = parseFloat(document.getElementById("price").value);

    if (!desc || isNaN(qty) || isNaN(price)) {
        alert("Enter valid item details");
        return;
    }

    const amount = qty * price;

    items.push({ description: desc, power, qty, price, amount });
    renderTable();
    clearItemFields();
}

function renderTable() {
    const tbody = document.getElementById("items-body");
    tbody.innerHTML = "";
    let total = 0;

    items.forEach((item, index) => {
        total += item.amount;

        const row = document.createElement("tr");
        row.dataset.index = index;

        if (index === selectedIndex) {
            row.classList.add("selected-row");
        }

        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${item.description}</td>
            <td>${item.power}</td>
            <td>${item.qty}</td>
            <td>${item.price.toFixed(2)}</td>
            <td>${item.amount.toFixed(2)}</td>
        `;

        tbody.appendChild(row);
    });

    document.getElementById("total").value = total.toFixed(2);
}


function clearItemFields() {
    // ❌ Do NOT clear description & price
    document.getElementById("power").value = "";
    document.getElementById("qty").value = "";

    // Optional: auto focus qty for fast entry
    document.getElementById("qty").focus();
}

function removeSelected() {
    if (selectedIndex === -1) {
        alert("Please select a row first");
        return;
    }

    items.splice(selectedIndex, 1);
    selectedIndex = -1;
    renderTable();
}


function clearItems() {
    if (!confirm("Clear all items?")) return;
    items = [];
    renderTable();
}
document.addEventListener("click", function (e) {
    const row = e.target.closest("#items-body tr");
    if (!row) return;

    selectedIndex = parseInt(row.dataset.index);
    renderTable(); // refresh highlight
});

// ================= INVOICE SUBMIT =================

function submitInvoice() {
    if (items.length === 0) {
        alert("Add at least one item");
        return;
    }

    const payload = {
        invoice_no: document.getElementById("invoice_no").value,
        date: document.getElementById("date").value,
        customer_id: document.getElementById("customer").value,
        items: items,
        print_letterhead: document.getElementById("letterhead").checked,
        print_ntn: document.getElementById("ntn").checked
    };

    fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (!data.success) {
            alert("PDF generation failed");
            return;
        }

        // ✅ MOBILE-SAFE OPEN
        if (isMobileDevice()) {
            // 📱 Mobile → same page (works perfectly)
            window.location.href = data.pdf_url;
        } else {
            // 🖥 Desktop → open in new tab
            window.open(data.pdf_url, "_blank");
        }
        

        // reset invoice
        items = [];
        renderTable();

        // update next invoice number
        fetch(`/next_invoice/${payload.customer_id}`)
            .then(res => res.json())
            .then(d => {
                document.getElementById("invoice_no").value = d.invoice_no;
            });
    })
    .catch(err => {
        console.error(err);
        alert("Server error");
    });
}


function toggleCustomerForm() {
    const box = document.getElementById("customer-form");
    box.style.display = box.style.display === "block" ? "none" : "block";
}

function toggleProductForm() {
    const box = document.getElementById("product-form");
    box.style.display = box.style.display === "block" ? "none" : "block";
}

function saveCustomer() {
    const name = document.getElementById("cust-name").value.trim();
    const address = document.getElementById("cust-address").value.trim();

    if (!name) {
        alert("Customer name required");
        return;
    }

    fetch("/add_customer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, address })
    }).then(() => location.reload());
}

function saveProduct() {
    const name = document.getElementById("prod-name").value.trim();
    const price = document.getElementById("prod-price").value;

    if (!name || !price) {
        alert("Enter product name & price");
        return;
    }

    fetch("/add_product", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, price })
    }).then(() => location.reload());
}

// ================= INVOICE AUTO LOGIC =================
document.getElementById("product").addEventListener("change", function () {
    if (!this.value) return;

    const [desc, price] = this.value.split("|");
    document.getElementById("desc").value = desc;
    document.getElementById("price").value = price;
});

document.addEventListener("DOMContentLoaded", () => {
    const invoiceInput = document.getElementById("invoice_no");
    const customerSelect = document.getElementById("customer");

    // 🔹 Detect manual invoice edit
    invoiceInput.addEventListener("input", () => {
        invoiceEdited = true;
    });

    // 🔹 Auto invoice only if NOT manually edited
    customerSelect.addEventListener("change", function () {
        if (invoiceEdited) return;

        fetch(`/next_invoice/${this.value}`)
            .then(res => res.json())
            .then(data => {
                invoiceInput.value = data.invoice_no;
            });
    });
});
