# Smart Dairy & Milk Tracking System

A comprehensive Flask-based web application for managing milk transactions, deliveries, and inventory for dairy businesses.

## Features

- **Multi-Role System**:
  - Milk Sellers: Record milk transactions with quality metrics and payment tracking
  - Bike Milk Sellers: Manage customer deliveries and payments
  - Dairy Holders: Track stock levels and manage bulk inventory

- **Quality Management**:
  - Track Fat Percentage and SNF (Solids-Not-Fat) metrics
  - Maintain quality records for all transactions

- **Stock Management**:
  - Record stock additions and removals
  - Track stock levels over time

- **Reporting and Analytics**:
  - Generate reports for transactions, deliveries, and stock levels
  - Export data to CSV for external analysis

## Installation

1. Create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # macOS/Linux
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python run.py
   ```

4. Access the application at `http://127.0.0.1:5000`

## Troubleshooting

If you encounter installation issues:

- Upgrade pip: `python -m pip install --upgrade pip`
- Try: `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt`
- For Windows execution policy issues: Run PowerShell as Administrator and execute `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

## Usage Guide

1. Register as one of three user types: Milk Seller, Bike Milk Seller, or Dairy Holder
2. Use the role-specific dashboard to manage milk-related activities
3. Generate reports and export data as needed

## Technical Stack

- **Backend**: Flask (Python)
- **Database**: SQLite
- **ORM**: SQLAlchemy
- **Authentication**: Flask-Login
- **Frontend**: Bootstrap 5

## Database Structure

The application uses SQLite with the following key models:

- **User**: Stores user authentication details and role information
- **MilkTransaction**: Records milk sales from sellers to dairy
- **DeliveryTransaction**: Records home deliveries by bike sellers
- **DairyStock**: Tracks inventory levels and movements in the dairy

## Development

### Project Structure
```
dairy-tracking-system/
├── app/
│   ├── __init__.py
│   ├── models/
│   │   ├── user.py
│   │   └── transactions.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── main.py
│   │   ├── milk_seller.py
│   │   ├── bike_seller.py
│   │   └── dairy_holder.py
│   ├── static/
│   │   └── css/
│   │       └── style.css
│   └── templates/
│       ├── auth/
│       ├── milk_seller/
│       ├── bike_seller/
│       └── dairy_holder/
├── run.py
└── requirements.txt
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 