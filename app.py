from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io
import os

# Try to import pandas, but handle gracefully if not available
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
# Use in-memory database for serverless environment
database_url = os.environ.get('DATABASE_URL', 'sqlite:///tools_tracker.db')
if 'vercel' in os.environ.get('VERCEL_ENV', '').lower() or os.path.exists('/tmp'):
    # Use /tmp for Vercel serverless environment
    database_url = 'sqlite:////tmp/tools_tracker.db'
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Tool(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    zone_name = db.Column(db.String(100), nullable=False)
    frt_name = db.Column(db.String(100), nullable=False)
    tool_type = db.Column(db.String(100), nullable=False)
    serial_number = db.Column(db.String(100), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    added_by = db.Column(db.String(200), nullable=True)  # Track who added the tool
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Tool {self.tool_type} - {self.zone_name}>'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        zone_name = request.form['zone_name']
        frt_name = request.form['frt_name']
        
        if zone_name and frt_name:
            session['user_zone'] = zone_name
            session['user_frt'] = frt_name
            flash(f'Welcome! You are now logged in to {zone_name} - {frt_name}', 'success')
            return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_zone' not in session or 'user_frt' not in session:
        return redirect(url_for('login'))
    
    user_zone = session['user_zone']
    user_frt = session['user_frt']
    
    # Get all tools for dashboard view (show all zones and FRTs)
    all_tools = Tool.query.order_by(Tool.zone_name, Tool.frt_name, Tool.created_at.desc()).all()
    
    # Define all possible zones and FRTs for complete view
    all_zones = ['COASTAL', 'NAVI MUME', 'NORTH GO', 'SOUTH GOA', 'KALYAN', 'VASAI', 'RAJKOT', 'OFFICE']
    all_frts = {
        'COASTAL': ['KHED', 'JAMSANDE', 'MURUD'],
        'NAVI MUME': ['BELAPUR-1', 'AIROLI', 'SHILPHATA', 'NAVI MUMBAI-SD'],
        'NORTH GO': ['MAPUSA', 'PANJIM', 'GOA CIVIL'],
        'SOUTH GOA': ['MADGAON', 'VERNA', 'CONCOLIM', 'SANQUELIM'],
        'KALYAN': ['SHRINGARTALE', 'AMBADI', 'KALYAN-SD'],
        'VASAI': ['BADLAPUR', 'BHIWANDI', 'KALYAN', 'BELAPUR-2', 'SANPADA-1', 'SANPADA-2', 'BOISAR', 'VASAI', 'TALASARI', 'VIRAR'],
        'RAJKOT': ['DHARI', 'KUDAL', 'MAHAD', 'ALIBAG', 'CHIPLUN', 'RAJAPUR'],
        'OFFICE': ['OFFICE']
    }
    
    # Group tools by zone and FRT with detailed statistics
    tools_by_location = {}
    zone_stats = {}
    frt_stats = {}
    tool_type_stats = {}
    total_tools = 0
    total_with_serial = 0
    total_with_remarks = 0
    
    # Initialize all zones and FRTs (even empty ones)
    for zone in all_zones:
        tools_by_location[zone] = {}
        zone_stats[zone] = {
            'total': 0,
            'with_serial': 0,
            'with_remarks': 0,
            'frts': set(),
            'tool_types': set(),
            'latest_tool': None,
            'oldest_tool': None,
            'empty_frts': set()
        }
        
        for frt in all_frts.get(zone, []):
            tools_by_location[zone][frt] = []
            frt_key = f"{zone}_{frt}"
            frt_stats[frt_key] = {
                'zone': zone,
                'frt': frt,
                'total': 0,
                'with_serial': 0,
                'with_remarks': 0,
                'tool_types': set(),
                'latest_tool': None,
                'oldest_tool': None,
                'has_tools': False
            }
            zone_stats[zone]['empty_frts'].add(frt)
    
    # Process actual tools
    for tool in all_tools:
        zone = tool.zone_name
        frt = tool.frt_name
        tool_type = tool.tool_type
        
        # Skip if zone or FRT not in predefined lists
        if zone not in all_zones or frt not in all_frts.get(zone, []):
            continue
        
        # Initialize tool type stats
        if tool_type not in tool_type_stats:
            tool_type_stats[tool_type] = {
                'total': 0,
                'zones': set(),
                'frts': set(),
                'with_serial': 0,
                'with_remarks': 0
            }
        
        # Add tool to location
        tools_by_location[zone][frt].append(tool)
        
        # Update zone stats
        total_tools += 1
        zone_stats[zone]['total'] += 1
        zone_stats[zone]['frts'].add(frt)
        zone_stats[zone]['tool_types'].add(tool_type)
        zone_stats[zone]['empty_frts'].discard(frt)  # Remove from empty set
        
        # Update FRT stats
        frt_key = f"{zone}_{frt}"
        frt_stats[frt_key]['total'] += 1
        frt_stats[frt_key]['tool_types'].add(tool_type)
        frt_stats[frt_key]['has_tools'] = True
        
        # Update tool type stats
        tool_type_stats[tool_type]['total'] += 1
        tool_type_stats[tool_type]['zones'].add(zone)
        tool_type_stats[tool_type]['frts'].add(frt)
        
        # Track serial numbers
        if tool.serial_number:
            total_with_serial += 1
            zone_stats[zone]['with_serial'] += 1
            frt_stats[frt_key]['with_serial'] += 1
            tool_type_stats[tool_type]['with_serial'] += 1
        
        # Track remarks
        if tool.remarks:
            total_with_remarks += 1
            zone_stats[zone]['with_remarks'] += 1
            frt_stats[frt_key]['with_remarks'] += 1
            tool_type_stats[tool_type]['with_remarks'] += 1
        
        # Track latest and oldest tools
        if tool.created_at:
            if zone_stats[zone]['latest_tool'] is None or tool.created_at > zone_stats[zone]['latest_tool'].created_at:
                zone_stats[zone]['latest_tool'] = tool
            if zone_stats[zone]['oldest_tool'] is None or tool.created_at < zone_stats[zone]['oldest_tool'].created_at:
                zone_stats[zone]['oldest_tool'] = tool
            
            if frt_stats[frt_key]['latest_tool'] is None or tool.created_at > frt_stats[frt_key]['latest_tool'].created_at:
                frt_stats[frt_key]['latest_tool'] = tool
            if frt_stats[frt_key]['oldest_tool'] is None or tool.created_at < frt_stats[frt_key]['oldest_tool'].created_at:
                frt_stats[frt_key]['oldest_tool'] = tool
    
    # Convert sets to counts and prepare data for template
    for zone in zone_stats:
        zone_stats[zone]['frt_count'] = len(zone_stats[zone]['frts'])
        zone_stats[zone]['tool_type_count'] = len(zone_stats[zone]['tool_types'])
        zone_stats[zone]['empty_frt_count'] = len(zone_stats[zone]['empty_frts'])
        zone_stats[zone]['total_frt_count'] = len(all_frts.get(zone, []))
        zone_stats[zone]['serial_percentage'] = round((zone_stats[zone]['with_serial'] / zone_stats[zone]['total']) * 100, 1) if zone_stats[zone]['total'] > 0 else 0
        zone_stats[zone]['remarks_percentage'] = round((zone_stats[zone]['with_remarks'] / zone_stats[zone]['total']) * 100, 1) if zone_stats[zone]['total'] > 0 else 0
        zone_stats[zone]['frt_coverage'] = round((zone_stats[zone]['frt_count'] / zone_stats[zone]['total_frt_count']) * 100, 1) if zone_stats[zone]['total_frt_count'] > 0 else 0
        del zone_stats[zone]['frts']  # Remove the set
        del zone_stats[zone]['tool_types']  # Remove the set
        del zone_stats[zone]['empty_frts']  # Remove the set
    
    for frt_key in frt_stats:
        frt_stats[frt_key]['tool_type_count'] = len(frt_stats[frt_key]['tool_types'])
        frt_stats[frt_key]['serial_percentage'] = round((frt_stats[frt_key]['with_serial'] / frt_stats[frt_key]['total']) * 100, 1) if frt_stats[frt_key]['total'] > 0 else 0
        frt_stats[frt_key]['remarks_percentage'] = round((frt_stats[frt_key]['with_remarks'] / frt_stats[frt_key]['total']) * 100, 1) if frt_stats[frt_key]['total'] > 0 else 0
        del frt_stats[frt_key]['tool_types']  # Remove the set
    
    for tool_type in tool_type_stats:
        tool_type_stats[tool_type]['zone_count'] = len(tool_type_stats[tool_type]['zones'])
        tool_type_stats[tool_type]['frt_count'] = len(tool_type_stats[tool_type]['frts'])
        tool_type_stats[tool_type]['serial_percentage'] = round((tool_type_stats[tool_type]['with_serial'] / tool_type_stats[tool_type]['total']) * 100, 1) if tool_type_stats[tool_type]['total'] > 0 else 0
        tool_type_stats[tool_type]['remarks_percentage'] = round((tool_type_stats[tool_type]['with_remarks'] / tool_type_stats[tool_type]['total']) * 100, 1) if tool_type_stats[tool_type]['total'] > 0 else 0
        del tool_type_stats[tool_type]['zones']  # Remove the set
        del tool_type_stats[tool_type]['frts']  # Remove the set
    
    # Get recent activity across all locations
    recent_tools = all_tools[:10]
    
    return render_template('dashboard.html', 
                         tools_by_location=tools_by_location,
                         zone_stats=zone_stats,
                         frt_stats=frt_stats,
                         tool_type_stats=tool_type_stats,
                         recent_tools=recent_tools,
                         all_zones=all_zones,
                         all_frts=all_frts,
                         user_zone=user_zone, 
                         user_frt=user_frt,
                         total_tools=total_tools,
                         total_with_serial=total_with_serial,
                         total_with_remarks=total_with_remarks)

@app.route('/export/excel')
def export_excel():
    if 'user_zone' not in session or 'user_frt' not in session:
        return redirect(url_for('login'))
    
    # Check if pandas is available
    if not PANDAS_AVAILABLE:
        flash('Excel export is not available. Please use CSV export instead.', 'warning')
        return redirect(url_for('dashboard'))
    
    # Get all tools for export
    all_tools = Tool.query.order_by(Tool.zone_name, Tool.frt_name, Tool.created_at.desc()).all()
    
    # Prepare data for Excel
    data = []
    for tool in all_tools:
        data.append({
            'Zone': tool.zone_name,
            'FRT': tool.frt_name,
            'Tool Type': tool.tool_type,
            'Serial Number': tool.serial_number or '',
            'Remarks': tool.remarks or '',
            'Created At': tool.created_at.strftime('%Y-%m-%d %H:%M:%S') if tool.created_at else '',
            'Updated At': tool.updated_at.strftime('%Y-%m-%d %H:%M:%S') if tool.updated_at else '',
            'Added By': session.get('user_zone', 'Unknown')
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Tools Inventory', index=False)
        
        # Get the workbook and worksheet for formatting
        workbook = writer.book
        worksheet = writer.sheets['Tools Inventory']
        
        # Adjust column widths
        column_widths = {
            'A': 15,  # Zone
            'B': 20,  # FRT
            'C': 20,  # Tool Type
            'D': 20,  # Serial Number
            'E': 30,  # Remarks
            'F': 20,  # Created At
            'G': 20,  # Updated At
            'H': 15   # Added By
        }
        
        for col, width in column_widths.items():
            worksheet.column_dimensions[col].width = width
        
        # Format header row
        for cell in worksheet[1]:
            cell.font = workbook.openpyxl.styles.Font(bold=True)
            cell.fill = workbook.openpyxl.styles.PatternFill(
                start_color="667eea",
                end_color="667eea",
                fill_type="solid"
            )
            cell.font = workbook.openpyxl.styles.Font(bold=True, color="FFFFFF")
        
        # Add borders to all cells
        thin_border = workbook.openpyxl.styles.Border(
            left=workbook.openpyxl.styles.Side(style='thin'),
            right=workbook.openpyxl.styles.Side(style='thin'),
            top=workbook.openpyxl.styles.Side(style='thin'),
            bottom=workbook.openpyxl.styles.Side(style='thin')
        )
        
        for row in worksheet.iter_rows():
            for cell in row:
                cell.border = thin_border
    
    output.seek(0)
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=tools_inventory_{}.xlsx'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return response

@app.route('/export/csv')
def export_csv():
    if 'user_zone' not in session or 'user_frt' not in session:
        return redirect(url_for('login'))
    
    # Get all tools for export
    all_tools = Tool.query.order_by(Tool.zone_name, Tool.frt_name, Tool.created_at.desc()).all()
    
    # Create CSV content
    csv_content = 'Zone,FRT,Tool Type,Serial Number,Remarks,Created At,Updated At,Added By\n'
    
    for tool in all_tools:
        csv_content += f'{tool.zone_name},{tool.frt_name},{tool.tool_type},"{tool.serial_number or ""}","{tool.remarks or ""}",{tool.created_at.strftime("%Y-%m-%d %H:%M:%S") if tool.created_at else ""},{tool.updated_at.strftime("%Y-%m-%d %H:%M:%S") if tool.updated_at else ""},{session.get("user_zone", "Unknown")}\n'
    
    # Create response
    response = make_response(csv_content)
    response.headers['Content-Disposition'] = 'attachment; filename=tools_inventory_{}.csv'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    response.headers['Content-type'] = 'text/csv'
    
    return response

@app.route('/')
def index():
    if 'user_zone' in session and 'user_frt' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/add', methods=['GET', 'POST'])
def add_tool():
    if 'user_zone' not in session or 'user_frt' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            tool_type = request.form['tool_type']
            serial_number = request.form.get('serial_number', '')
            remarks = request.form.get('remarks', '')
            
            if not tool_type:
                flash('Tool Type is required!', 'error')
                return render_template('add_tool.html')
            
            new_tool = Tool(
                zone_name=session['user_zone'], 
                frt_name=session['user_frt'], 
                tool_type=tool_type,
                serial_number=serial_number,
                added_by=f"{session['user_zone']} - {session['user_frt']}",
                remarks=remarks
            )
            db.session.add(new_tool)
            db.session.commit()
            flash('Tool added successfully!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            print(f"Error adding tool: {e}")
            db.session.rollback()
            flash(f'Error adding tool: {str(e)}', 'error')
            return render_template('add_tool.html')
    
    return render_template('add_tool.html', 
                         user_zone=session['user_zone'], 
                         user_frt=session['user_frt'])

@app.route('/select_location', methods=['GET', 'POST'])
def select_location():
    if request.method == 'POST':
        zone_name = request.form['zone_name']
        frt_name = request.form['frt_name']
        return redirect(url_for('add_tool_for_location', zone_name=zone_name, frt_name=frt_name))
    
    return render_template('select_location.html')

@app.route('/add_tool/<zone_name>/<frt_name>', methods=['GET', 'POST'])
def add_tool_for_location(zone_name, frt_name):
    if request.method == 'POST':
        tool_type = request.form['tool_type']
        serial_number = request.form.get('serial_number', '')
        remarks = request.form.get('remarks', '')
        
        if not tool_type:
            flash('Tool Type is required!', 'error')
            return render_template('add_tool_for_location.html', zone_name=zone_name, frt_name=frt_name)
        
        new_tool = Tool(
            zone_name=zone_name, 
            frt_name=frt_name, 
            tool_type=tool_type,
            serial_number=serial_number,
            remarks=remarks
        )
        db.session.add(new_tool)
        db.session.commit()
        flash('Tool added successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('add_tool_for_location.html', zone_name=zone_name, frt_name=frt_name)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_tool(id):
    tool = Tool.query.get_or_404(id)
    
    if request.method == 'POST':
        tool.zone_name = request.form['zone_name']
        tool.frt_name = request.form['frt_name']
        tool.tool_type = request.form['tool_type']
        tool.serial_number = request.form.get('serial_number', '')
        tool.remarks = request.form.get('remarks', '')
        
        if not tool.zone_name or not tool.frt_name or not tool.tool_type:
            flash('Zone Name, FRT Name, and Tool Type are required!', 'error')
            return render_template('edit.html', tool=tool)
        
        db.session.commit()
        flash('Tool updated successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('edit.html', tool=tool)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_tool(id):
    if 'user_zone' not in session or 'user_frt' not in session:
        return redirect(url_for('login'))
    
    tool = Tool.query.get_or_404(id)
    
    # Check if tool belongs to current user's location
    if tool.zone_name != session['user_zone'] or tool.frt_name != session['user_frt']:
        flash('You can only delete tools from your location!', 'error')
        return redirect(url_for('dashboard'))
    
    db.session.delete(tool)
    db.session.commit()
    flash('Tool deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/view/<int:id>')
def view_tool(id):
    tool = Tool.query.get_or_404(id)
    return render_template('view.html', tool=tool)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
