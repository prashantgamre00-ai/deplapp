from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, make_response
from datetime import datetime
from dotenv import load_dotenv
import io
import os
from supabase import create_client, Client

load_dotenv() 

# Try to import pandas, but handle gracefully if not available
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Warning: SUPABASE_URL or SUPABASE_KEY is missing!")

supabase: Client = create_client(SUPABASE_URL or "", SUPABASE_KEY or "")

# Wrapper class to make dictionaries behave like SQLAlchemy models in templates
class Tool:
    def __init__(self, **entries):
        self.__dict__.update(entries)
        # Parse ISO strings to datetime
        if hasattr(self, 'created_at') and isinstance(self.created_at, str):
            try:
                self.created_at = datetime.fromisoformat(self.created_at.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                pass
        if hasattr(self, 'updated_at') and isinstance(self.updated_at, str):
            try:
                self.updated_at = datetime.fromisoformat(self.updated_at.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                pass

    def __repr__(self):
        return f'<Tool {getattr(self, "tool_type", "Unknown")} - {getattr(self, "zone_name", "Unknown")}>'

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
    try:
        response = supabase.table('tool').select('*').order('zone_name').order('frt_name').order('created_at', desc=True).execute()
        all_tools = [Tool(**item) for item in response.data]
    except Exception as e:
        print(f"Error fetching tools: {e}")
        all_tools = []
    
    # Define all possible zones and FRTs for complete view
    all_zones = ['COASTAL', 'NAVI MUMBAI', 'NORTH GOA', 'SOUTH GOA', 'KALYAN', 'VASAI', 'RAJKOT', 'OFFICE']
    all_frts = {
        'COASTAL': ['KHED', 'JAMSANDE', 'MURUD'],
        'NAVI MUMBAI': ['BELAPUR-1','BELAPUR-2','AIROLI','SANPADA-1', 'SANPADA-2', 'SHILPHATA', 'NAVI MUMBAI-SD','KOPARKHAIRANE'],
        'NORTH GOA': ['MAPUSA', 'PANJIM', 'GOA CIVIL'],
        'SOUTH GOA': ['MADGAON', 'VERNA', 'CONCOLIM', 'SANQUELIM'],
        'KALYAN': ['SHRINGARTALE', 'AMBADI', 'KALYAN-SD'],
        'VASAI': ['BADLAPUR', 'BHIWANDI', 'KALYAN', 'BOISAR', 'VASAI', 'TALASARI', 'VIRAR'],
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
        zone = getattr(tool, 'zone_name', None)
        frt = getattr(tool, 'frt_name', None)
        tool_type = getattr(tool, 'tool_type', None)
        
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
        if getattr(tool, 'serial_number', None):
            total_with_serial += 1
            zone_stats[zone]['with_serial'] += 1
            frt_stats[frt_key]['with_serial'] += 1
            tool_type_stats[tool_type]['with_serial'] += 1
        
        # Track remarks
        if getattr(tool, 'remarks', None):
            total_with_remarks += 1
            zone_stats[zone]['with_remarks'] += 1
            frt_stats[frt_key]['with_remarks'] += 1
            tool_type_stats[tool_type]['with_remarks'] += 1
        
        # Track latest and oldest tools
        if getattr(tool, 'created_at', None):
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
    
    if not PANDAS_AVAILABLE:
        flash('Excel export is not available. Please use CSV export instead.', 'warning')
        return redirect(url_for('dashboard'))
    
    try:
        response = supabase.table('tool').select('*').order('zone_name').order('frt_name').order('created_at', desc=True).execute()
        all_tools = [Tool(**item) for item in response.data]
    except Exception as e:
        print(f"Error fetching tools: {e}")
        all_tools = []
    
    data = []
    for tool in all_tools:
        data.append({
            'Zone': getattr(tool, 'zone_name', ''),
            'FRT': getattr(tool, 'frt_name', ''),
            'Tool Type': getattr(tool, 'tool_type', ''),
            'Serial Number': getattr(tool, 'serial_number', '') or '',
            'Remarks': getattr(tool, 'remarks', '') or '',
            'Created At': tool.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(tool, 'created_at') and tool.created_at else '',
            'Updated At': tool.updated_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(tool, 'updated_at') and tool.updated_at else '',
            'Added By': getattr(tool, 'added_by', 'Unknown')
        })
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Tools Inventory', index=False)
        workbook = writer.book
        worksheet = writer.sheets['Tools Inventory']
        
        column_widths = {
            'A': 15, 'B': 20, 'C': 20, 'D': 20, 'E': 30, 'F': 20, 'G': 20, 'H': 25
        }
        for col, width in column_widths.items():
            worksheet.column_dimensions[col].width = width
        
        for cell in worksheet[1]:
            cell.font = workbook.openpyxl.styles.Font(bold=True, color="FFFFFF")
            cell.fill = workbook.openpyxl.styles.PatternFill(start_color="667eea", end_color="667eea", fill_type="solid")
        
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
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=tools_inventory_{}.xlsx'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
    response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return response

@app.route('/export/csv')
def export_csv():
    if 'user_zone' not in session or 'user_frt' not in session:
        return redirect(url_for('login'))
    
    try:
        response = supabase.table('tool').select('*').order('zone_name').order('frt_name').order('created_at', desc=True).execute()
        all_tools = [Tool(**item) for item in response.data]
    except Exception as e:
        print(f"Error fetching tools: {e}")
        all_tools = []
    
    csv_content = 'Zone,FRT,Tool Type,Serial Number,Remarks,Created At,Updated At,Added By\n'
    
    for tool in all_tools:
        created_at_str = tool.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(tool, 'created_at') and tool.created_at else ""
        updated_at_str = tool.updated_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(tool, 'updated_at') and tool.updated_at else ""
        csv_content += f'{getattr(tool,"zone_name","")},{getattr(tool,"frt_name","")},{getattr(tool,"tool_type","")},"{getattr(tool,"serial_number","") or ""}","{getattr(tool,"remarks","") or ""}",{created_at_str},{updated_at_str},{getattr(tool,"added_by","Unknown")}\n'
    
    response = make_response(csv_content)
    response.headers['Content-Disposition'] = 'attachment; filename=tools_inventory_{}.csv'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
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
            
            new_tool = {
                'zone_name': session['user_zone'], 
                'frt_name': session['user_frt'], 
                'tool_type': tool_type,
                'serial_number': serial_number,
                'added_by': f"{session['user_zone']} - {session['user_frt']}",
                'remarks': remarks
            }
            supabase.table('tool').insert(new_tool).execute()
            flash('Tool added successfully!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            print(f"Error adding tool: {e}")
            flash(f'Error adding tool: {str(e)}', 'error')
            return render_template('add_tool.html')
    
    return render_template('add_tool.html', user_zone=session['user_zone'], user_frt=session['user_frt'])

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
        
        new_tool = {
            'zone_name': zone_name, 
            'frt_name': frt_name, 
            'tool_type': tool_type,
            'serial_number': serial_number,
            'remarks': remarks
        }
        try:
            supabase.table('tool').insert(new_tool).execute()
            flash('Tool added successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error adding tool: {str(e)}', 'error')
    
    return render_template('add_tool_for_location.html', zone_name=zone_name, frt_name=frt_name)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_tool(id):
    try:
        response = supabase.table('tool').select('*').eq('id', id).execute()
        if not response.data:
            return "Tool not found", 404
        tool = Tool(**response.data[0])
    except Exception as e:
        return f"Error: {e}", 500
    
    if request.method == 'POST':
        zone_name = request.form['zone_name']
        frt_name = request.form['frt_name']
        tool_type = request.form['tool_type']
        serial_number = request.form.get('serial_number', '')
        remarks = request.form.get('remarks', '')
        
        if not zone_name or not frt_name or not tool_type:
            flash('Zone Name, FRT Name, and Tool Type are required!', 'error')
            return render_template('edit.html', tool=tool)
        
        updates = {
            'zone_name': zone_name,
            'frt_name': frt_name,
            'tool_type': tool_type,
            'serial_number': serial_number,
            'remarks': remarks,
            'updated_at': datetime.utcnow().isoformat()
        }
        try:
            supabase.table('tool').update(updates).eq('id', id).execute()
            flash('Tool updated successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error updating tool: {str(e)}', 'error')
            
    return render_template('edit.html', tool=tool)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_tool(id):
    if 'user_zone' not in session or 'user_frt' not in session:
        return redirect(url_for('login'))
    
    try:
        response = supabase.table('tool').select('*').eq('id', id).execute()
        if not response.data:
            return "Tool not found", 404
        tool = Tool(**response.data[0])
        
        # Check if tool belongs to current user's location
        if getattr(tool, 'zone_name', '') != session['user_zone'] or getattr(tool, 'frt_name', '') != session['user_frt']:
            flash('You can only delete tools from your location!', 'error')
            return redirect(url_for('dashboard'))
        
        supabase.table('tool').delete().eq('id', id).execute()
        flash('Tool deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting tool: {str(e)}', 'error')
        
    return redirect(url_for('dashboard'))

@app.route('/view/<int:id>')
def view_tool(id):
    try:
        response = supabase.table('tool').select('*').eq('id', id).execute()
        if not response.data:
            return "Tool not found", 404
        tool = Tool(**response.data[0])
        return render_template('view.html', tool=tool)
    except Exception as e:
        return f"Error: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)
