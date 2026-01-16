import os
import json
import logging
import re
from urllib.parse import urlparse

from markupsafe import Markup
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
# Imports necessários para as views do Admin
from wtforms.fields import PasswordField, TextAreaField, IntegerField, StringField

# --- Configuração Inicial ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'infografico.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'SUA_CHAVE_SECRETA_SUPER_FORTE_AQUI_V12_TAGS_REFINADAS_COMPLETAS')
db = SQLAlchemy(app)
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# --- Configuração do Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "info"

# --- Modelos do Banco de Dados ---
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class TimelineEvent(db.Model):
    __tablename__ = 'timeline_event'
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(50), nullable=False)
    sub_section = db.Column(db.String(50), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    text = db.Column(db.Text, nullable=False)
    images_json = db.Column(db.Text, nullable=True)
    corroboration = db.Column(db.Text, nullable=True)

    @property
    def images(self):
        if self.images_json:
            try:
                return json.loads(self.images_json)
            except json.JSONDecodeError:
                app.logger.error(f"Erro JSON TimelineEvent id {self.id}: {self.images_json}")
                return []
        return []

    @images.setter
    def images(self, image_list):
        if image_list and isinstance(image_list, list):
            self.images_json = json.dumps(image_list)
        elif not image_list:
            self.images_json = json.dumps([])
        else:
            app.logger.warning(f"Tipo inválido 'images' TimelineEvent id {self.id if self.id else 'Novo'}")
            self.images_json = json.dumps([])

    def to_dict(self):
        return {
            'id': self.id, 'section': self.section, 'sub_section': self.sub_section, 
            'year': self.year, 'title': self.title, 'text': self.text, 
            'images': self.images, 'corroboracao': self.corroboration
        }

    def __repr__(self):
        return f'<TimelineEvent {self.id} - {self.title[:30]}>'

class GalleryImage(db.Model):
    __tablename__ = 'gallery_image'
    id = db.Column(db.Integer, primary_key=True)
    chronological_order = db.Column(db.Integer, nullable=True, default=0)
    file_name = db.Column(db.String(255), nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=True)
    corroboration_text = db.Column(db.Text, nullable=True)
    admin_assigned_section = db.Column(db.String(100), nullable=True, default='Geral')
    tags = db.Column(db.String(500), nullable=True)

    def get_detected_topics(self):
        detected = set()
        text_to_scan = []
        if self.title: text_to_scan.append(self.title.lower())
        if self.corroboration_text: text_to_scan.append(self.corroboration_text.lower())
        if self.file_name: text_to_scan.append(os.path.splitext(self.file_name)[0].lower().replace('_', ' ').replace('-', ' '))
        if self.admin_assigned_section and self.admin_assigned_section != 'Geral': text_to_scan.append(self.admin_assigned_section.lower())
        
        full_text_to_scan = " ".join(text_to_scan)
        
        if re.search(r'\bpanceri\b', full_text_to_scan): detected.add("Panceri")
        if re.search(r'\bpompeia\b', full_text_to_scan) or re.search(r'\bpizzamiglio\b', full_text_to_scan): detected.add("Pompeia")
        if re.search(r'\bscavino\b', full_text_to_scan) or re.search(r'\bbertuzzi\b', full_text_to_scan): detected.add("Scavino & Bertuzzi")
        
        if not detected and self.admin_assigned_section in ["Panceri", "Pompeia", "Scavino & Bertuzzi"]:
            detected.add(self.admin_assigned_section)
            
        return list(detected) if detected else ["Geral"]

    def get_tags_list(self):
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()] if self.tags and self.tags.strip() else []

    def to_dict(self):
        return {
            'id': self.id, 'chronological_order': self.chronological_order, 
            'fileName': self.file_name, 'title': self.title, 
            'corroboration': self.corroboration_text, 
            'admin_assigned_section': self.admin_assigned_section, 
            'detected_topics': self.get_detected_topics(), 'tags': self.get_tags_list()
        }

    def __repr__(self):
        return f'<GalleryImage {self.id} - Tags: {self.tags}>'

# --- Configuração do Flask-Admin ---
class ProtectedAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.url))
        return super(ProtectedAdminIndexView, self).index()

class ProtectedModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated

    def inaccessible_callback(self, name, **kwargs):
        flash("Por favor, faça login.", "warning")
        return redirect(url_for('login', next=request.url))

class TimelineEventAdminView(ProtectedModelView):
    column_list = ('id', 'section', 'sub_section', 'year', 'title')
    column_searchable_list = ('title', 'text', 'section', 'sub_section', 'year')
    column_filters = ('section', 'sub_section', 'year')
    column_editable_list = ('year',)
    form_columns = ('section', 'sub_section', 'year', 'title', 'text', 'images_json', 'corroboration')
    form_overrides = {
        'text': TextAreaField, 
        'images_json': TextAreaField, 
        'corroboration': TextAreaField, 
        'year': IntegerField
    }
    form_args = {
        'text': {'render_kw': {'rows': 10}}, 
        'images_json': {'render_kw': {'rows': 3}, 'description': 'JSON: ["img1.jpg"]'}, 
        'corroboration': {'render_kw': {'rows': 8}}
    }
    def __init__(self, session, **kwargs):
        super(TimelineEventAdminView, self).__init__(TimelineEvent, session, name='Eventos Timeline', **kwargs)

class GalleryImageAdminView(ProtectedModelView):
    column_list = ('id', 'admin_assigned_section', 'chronological_order', 'file_name', 'title', 'tags')
    column_searchable_list = ('file_name', 'title', 'admin_assigned_section', 'tags')
    column_filters = ('admin_assigned_section', 'tags')
    column_editable_list = ('admin_assigned_section', 'chronological_order', 'title', 'corroboration_text', 'tags')
    form_columns = ('admin_assigned_section', 'chronological_order', 'file_name', 'title', 'corroboration_text', 'tags')
    form_overrides = {
        'corroboration_text': TextAreaField, 
        'tags': StringField
    }
    form_args = {
        'corroboration_text': {'render_kw': {'rows': 5}}, 
        'admin_assigned_section': {'description': 'Ex: Panceri, Pompeia, Geral'}, 
        'tags': {'description': 'Tags: doc, fábrica, família'}
    }
    def __init__(self, session, **kwargs):
        super(GalleryImageAdminView, self).__init__(GalleryImage, session, name='Imagens Galeria', **kwargs)

class UserAdminView(ProtectedModelView):
    column_list = ('id', 'username')
    form_columns = ('username',)
    form_extra_fields = {'password': PasswordField('Nova Senha')}
    form_create_rules = ('username', 'password')
    form_edit_rules = ('username', 'password')

    def on_model_change(self, form, model, is_created):
        if form.password.data:
            model.set_password(form.password.data)
        elif is_created and not form.password.data:
            flash('Senha é obrigatória para criar um novo usuário.', 'error')
            # Evita a criação do usuário sem senha, mas de forma mais branda que um 'raise'
            # A validação ideal seria via WTForms validators
            
    def __init__(self, session, **kwargs):
        super(UserAdminView, self).__init__(User, session, name='Usuários', **kwargs)

admin = Admin(app, name='Painel Admin', template_mode='bootstrap4', index_view=ProtectedAdminIndexView())
admin.add_view(TimelineEventAdminView(db.session))
admin.add_view(GalleryImageAdminView(db.session))
admin.add_view(UserAdminView(db.session))


initial_data_to_seed = {
    "panceri": [
        {
            "sub_section": "jose_panceri_pai",
            "year": 1858,
            "title": "Origens e Emigração de Joseph Panceri (1858 - ~1885)",
            "text": "Nascido em Concorezzo, perto de Milão, em 1858, Joseph Panceri, já operário têxtil na Itália, emigrou para o Brasil por volta de 1885. Casou-se com Virgínia Perolini em 1882 e veio acompanhado pela esposa e pelos filhos Luiz e Carolina Francisca. A família estabeleceu-se inicialmente na 6ª Légua, Caxias do Sul, dedicando-se à agricultura.",
            "images": ["9e02599a-823a-484c-a647-8e8205610d38.jpg", "História familia Panceri 1.jpg"],
            "corroboracao": "Informações sobre a emigração de Joseph Panceri em 1858 são baseadas no resumo histórico detalhado da família. As imagens '9e02599a-823a-484c-a647-8e8205610d38.jpg' (retrato da Família Panceri na 6ª Légua) e o documento 'História familia Panceri 1.jpg' fornecem detalhes cruciais sobre sua origem italiana, a viagem para o Brasil e o estabelecimento inicial em Caxias do Sul, onde se dedicaram à agricultura."
        },
        {
            "sub_section": "jose_panceri_pai",
            "year": 1890,
            "title": "Retorno à Tecelagem e Primeiros Empreendimentos em Rio Grande (até ~1890)",
            "text": "A paixão pela tecelagem levou Joseph a procurar trabalho na área. Atuou no Lanifício São Pedro de Abramo Eberle e com Henrique Cantergiani em Caxias. Posteriormente, mudou-se para Rio Grande, onde, até por volta de 1890, trabalhou como contramestre na fábrica de tecidos Rheingantz (ligada a Abramo Eberle), juntamente com sua esposa Virgínia.",
            "images": ["História familia Panceri 1.jpg"],
            "corroboracao": "A trajetória profissional de Joseph Panceri, incluindo seu trabalho no Lanifício São Pedro com Abramo Eberle e Henrique Cantergiani, e posteriormente como contramestre na fábrica Rheingantz em Rio Grande até aproximadamente 1890, é corroborada principalmente pelo documento histórico 'História familia Panceri 1.jpg'."
        },
        {
            "sub_section": "jose_panceri_pai",
            "year": 1891,
            "title": "Produção Própria e Inovação na 6ª Légua (Pós-1890)",
            "text": "Com as economias feitas, regressou à 6ª Légua. Em casa, construiu teares de madeira e acessórios (lançadeiras, pentes) com materiais locais como cipós e taquaras. Seus primeiros produtos comercializáveis foram 'fachas para enrolar nenês' e a 'sobre-chincha' (algodão, depois lã, com nome bordado), enviadas para Porto Alegre via São Sebastião do Caí. Palas e cobertores também fizeram parte desta produção inicial.",
            "images": ["Historia familia Panceri 2.jpg"],
            "corroboracao": "O início da produção artesanal de Joseph Panceri e sua notável engenhosidade na construção de teares manuais e acessórios com materiais locais (cipós, taquaras) na 6ª Légua, após 1890, são detalhados no documento 'Historia familia Panceri 2.jpg'. Este documento também menciona seus primeiros produtos comercializáveis, como 'fachas para enrolar nenês' e a 'sobre-chincha'."
        },
        {
            "sub_section": "jose_panceri_pai",
            "year": 1899,
            "title": "Primeira Tecelagem Familiar de Joseph Panceri e Reconhecimento (1899/1910)",
            "text": "Em 1899, Joseph Panceri instalou sua primeira tecelagem na Rua Ernesto Alves. Este empreendimento essencialmente familiar, focada em sedas finas, foi posteriormente denominada 'Tecelagem Nossa Senhora de Pompeia' em alguns relatos (como o artigo 'A Trama dos Fios'). Uma publicação de 1910 descreve sua fábrica já com quatro teares a pedal, reconhecida com prémios em exposições, apesar dos desafios na obtenção de matéria-prima. Panceri destacava o melhor rendimento da seda local.",
            "images": ["A trama dos fios - 1.jpg", "Historia Panceri 1 - 1910.png", "Historia Panceri 2 - 1910.png"],
            "corroboracao": "A fundação da primeira tecelagem por Joseph Panceri em 1899, na Rua Ernesto Alves, e seu reconhecimento inicial são corroborados pelo artigo 'A Trama dos Fios' (imagem 'A trama dos fios - 1.jpg'). As publicações de 1910 (imagens 'Historia Panceri 1 - 1910.png' e 'Historia Panceri 2 - 1910.png') descrevem a fábrica com quatro teares a pedal e os prêmios recebidos em exposições, apesar das dificuldades com matéria-prima. A denominação 'Tecelagem Nossa Senhora de Pompeia' para este empreendimento inicial é citada em algumas fontes."
        },
        {
            "sub_section": "jose_panceri_pai",
            "year": 1900,
            "title": "Desafios Familiares e Segundo Casamento (Início Séc. XX)",
            "text": "Joseph enfrentou o falecimento de seus pais e da primeira esposa, Virgínia, assumindo os cuidados dos quatro filhos (Carolina, Luiz, Pasqual e Josefina). Casou-se posteriormente com Josefina De Gregoria, com quem teve mais filhos, incluindo Adelina (futura esposa de Luiz Pizzamiglio), José (Júnior) e Agostinho.",
            "images": ["Historia familia Panceri 2.jpg"],
            "corroboracao": "Eventos pessoais significativos na vida de Joseph Panceri no início do século XX, como o falecimento de entes queridos e seu segundo casamento com Josefina De Gregoria, que resultou no nascimento de mais filhos, são narrados no documento 'Historia familia Panceri 2.jpg'."
        },
        {
            "sub_section": "jose_panceri_pai",
            "year": 1909,
            "title": "Mudança para Caxias, Foco na Seda e Parceria com Eberle (1909)",
            "text": "Após o falecimento da segunda esposa, Josefina De Gregoria, em 1909, Joseph Panceri transferiu-se para o núcleo urbano de Caxias do Sul, instalando sua indústria focada na seda. Tentou incentivar a sericicultura local, cultivando amoreiras para pequena produção de casulos, com os quais fazia lenços e palas. Um anúncio de 1909 de sua 'Fabbrica di tessuti di seta' indicava Abramo Eberle & C. como representantes para compra de casulos. No mesmo ano, é referido como sócio de Luiz Michielin.",
            "images": ["Giussepe a procura de casulo, representante EBERLE - 1909.png", "Historia familia Panceri 3.jpg", "A trama dos fios - 1.jpg"],
            "corroboracao": "A consolidação da indústria de seda de Joseph Panceri em Caxias do Sul em 1909, suas tentativas de fomentar a sericicultura local e as parcerias comerciais são evidenciadas pelo anúncio ('Giussepe a procura de casulo...EBERLE - 1909.png') que o ligava a Abramo Eberle, e pelos relatos nos documentos 'Historia familia Panceri 3.jpg' e 'A trama dos fios - 1.jpg'."
        },
        {
            "sub_section": "jose_panceri_pai",
            "year": 1911,
            "title": "Modernização e Viagens à Itália (1911)",
            "text": "Em 1911, Joseph Panceri viajou à Itália (Milão) e retornou com teares modernos. Devido à dificuldade na produção local de seda, passou a importar o fio diretamente da Itália, buscando constante aperfeiçoamento técnico.",
            "images": ["Historia familia Panceri 3.jpg"],
            "corroboracao": "A busca por modernização e aperfeiçoamento técnico, incluindo a viagem de Joseph Panceri à Itália em 1911 para adquirir teares modernos e a subsequente importação de fio de seda, é detalhada no documento 'Historia familia Panceri 3.jpg'."
        },
        {
            "sub_section": "jose_panceri_pai",
            "year": 1917,
            "title": "Reconhecimento, Envolvimento Comunitário e Casamento da Filha Adelina (1917)",
            "text": "Em 1917, um 'fino pala de sêda' de seu estabelecimento foi ofertado ao Cônsul Geral do Uruguai. Joseph Panceri era presidente da Sociedade Recreio Dante, com Abramo Eberle como tesoureiro. Neste ano, sua filha Adelina casou-se com Luiz Pizzamiglio.",
            "images": ["Doação Fábrica Panceri - 1917 por Giussepe Panceri.jpg", "A ligação entre Panceri e Eberle, dentro e fora dos comércios.png", "A trama dos fios - 1.jpg"],
            "corroboracao": "O prestígio dos produtos de Joseph Panceri em 1917 é evidenciado pela doação de um pala de seda ao Cônsul Uruguaio ('Doação Fábrica Panceri...jpg'). Seu envolvimento comunitário como presidente da Sociedade Recreio Dante, ao lado de Abramo Eberle, é mostrado em 'A ligação entre Panceri e Eberle...png'. O casamento de sua filha Adelina com Luiz Pizzamiglio, um evento familiar chave, também ocorreu neste ano, conforme 'A trama dos fios - 1.jpg'."
        },
        {
            "sub_section": "jose_panceri_pai",
            "year": 1921,
            "title": "José Panceri & Cia. com Luiz Pizzamiglio (Década de 1920)",
            "text": "Na década de 1920, a empresa José Panceri & Cia. contava com Luiz Pizzamiglio como sócio (1921) e gerente (1929). Em 1921, um 'custoso palla de seda' da fábrica foi presenteado ao Presidente Borges de Medeiros. Em 1929, mesmo em crise, a fábrica na Rua Ernesto Alves possuía 32 teares (5 elétricos), produzindo diversos artigos de seda com qualidade. Antonio Perio era um técnico importante.",
            "images": ["Doação Fábrica Panceri - 1921 por Giussepe Panceri2.jpg", "Relato panceri 1 - 12_09_1929.png", "Relato panceri 2 - 12_09_1929.png", "Relato panceri 3 - 12_09_1929.png", "Relato panceri 4 - 12_09_1929.png"],
            "corroboracao": "A gestão de Luiz Pizzamiglio na José Panceri & Cia. durante a década de 1920, incluindo a doação de um produto ao Presidente Borges de Medeiros em 1921 ('Doação Fábrica Panceri - 1921...jpg'), e a descrição da fábrica em 1929 com seus teares e a menção ao técnico Antonio Perio, são detalhadas nos relatos de jornal ('Relato panceri 1-4 - 12_09_1929.png')."
        },
        {
            "sub_section": "jose_panceri_pai",
            "year": 1918, # Ano de fundação de "A Panceri" é um pouco incerto, mas após 1917
            "title": "Fundação da 'A Panceri' e Legado Final (Pós-1917 - 1943)",
            "text": "Após vender a Tecelagem Nossa Senhora de Pompeia a Luiz Pizzamiglio, Joseph Panceri fundou a 'A Panceri', diversificando com colchas de seda artificial ('Sol Nascente'), cetins e palas. A empresa prosperou durante as Guerras Mundiais, fabricando até tecidos para paraquedas. Joseph Panceri faleceu em 23 de abril de 1943, aos 84 anos.",
            "images": ["A trama dos fios - 1.jpg", "Giuseppe e o inicio dos irmaos panceri.png", "Historia familia Panceri 3.jpg"],
            "corroboracao": "O último empreendimento de Joseph Panceri, a 'A Panceri', sua diversificação de produtos e o período de prosperidade, inclusive durante as Guerras, são descritos em 'A trama dos fios - 1.jpg' e 'Historia familia Panceri 3.jpg'. Seu falecimento em 1943 é um marco final, também referenciado nestas fontes e em 'Giuseppe e o inicio dos irmaos panceri.png'."
        },
        {
            "sub_section": "irmaos_panceri_ltda",
            "year": 1928,
            "title": "Atuação dos Filhos e Fundação da 'Irmãos Panceri' (1912, 1928-1929)",
            "text": "Os filhos José Panceri Júnior e Agostinho Panceri atuavam como 'Irmãos Panceri' desde 1912. Em 1928, fundaram uma nova fábrica na Rua Saboia, um 'estabelecimento modelo' para tecelagem de seda. Em 1929, já operando, receberam modernos teares elétricos da França e Suíça.",
            "images": ["Giuseppe e o inicio dos irmaos panceri.png", "Relato panceri - 20_09_1929.png", "image.png"], # ID: 97a01ae7... é "image.png"
            "corroboracao": "O estabelecimento da fábrica dos Irmãos Panceri na Rua Saboia em 1928 e a subsequente modernização com teares elétricos importados em 1929 são documentados em 'Giuseppe e o inicio dos irmaos panceri.png', 'Relato panceri - 20_09_1929.png', e no artigo 'image.png' (ID: 97a01ae7...)."
        },
        {
            "sub_section": "irmaos_panceri_ltda",
            "year": 1931,
            "title": "Presença e Reconhecimento da Irmãos Panceri (Década de 1930-1950)",
            "text": "A 'Irmãos Panceri' foi listada como exportadora em 1931 e produtora de tecidos de seda em 1937 (junto com Pizzamiglio e Scavino). Em ~1942, tinha 30 operários. Em 1950, seu stand na Festa da Uva foi premiado. Em 1958, constava no edital do Sindicato Têxtil.",
            "images": ["As Fábricas coexistiram 4 - 1931.png", "As Fábricas coexistiram 5 - 1937.png", "As Fábricas coexistiram 2 - 1942.png", "Stand Irmaos Panceri - 1950.png", "As Fábricas coexistiram - 1958.png"],
            "corroboracao": "As atividades e o reconhecimento da Irmãos Panceri ao longo das décadas de 1930 a 1950 são evidenciados por sua listagem como exportadora em 1931 ('As Fábricas coexistiram 4 - 1931.png'), produtora de seda em 1937 ('As Fábricas coexistiram 5 - 1937.png'), o número de operários em 1942 ('As Fábricas coexistiram 2 - 1942.png'), o prêmio na Festa da Uva de 1950 ('Stand Irmaos Panceri - 1950.png') e sua menção no edital do Sindicato Têxtil em 1958 ('As Fábricas coexistiram - 1958.png')."
        },
        {
            "sub_section": "irmaos_panceri_ltda",
            "year": 1956,
            "title": "Tecelagem Panceri Ltda.: Gestão dos Netos e Atividade (Décadas 1950-1960)",
            "text": "A empresa evoluiu para Tecelagem Panceri Ltda., dirigida pelos netos do fundador (Henrique Panceri, Alfredo Furlan, Lya Panceri, Dino Dal Pont, Ary e Lauro Panceri). Em 1956, é vista em foto panorâmica. Em 1958, saudou o Presidente Gronchi. Anúncios de Natal de 1962, 1966 e 1969 mostram a empresa na Rua Vereador Mário Pezzi, 458, produzindo artigos de Seda, Raion e Nylon. Em 1967, participou de curso de desenho industrial.",
            "images": ["As Fábricas coexistiram 3 - 1956.png", "Fabricas e coexistência - 13_09_1958.jpg", "image.png", "image.png", "image.png", "Curso para desenhos - 1967.png"], # Anúncios: Panceri Natal 1962 (ID: 1bcc3aaf), Panceri Natal 1966 (ID: cdc5e0bd), Panceri Natal 1969 (ID: 6ac71e08)
            "corroboracao": "A continuidade da Tecelagem Panceri Ltda. sob a gestão da terceira geração da família e suas atividades nas décadas de 1950 e 1960 são documentadas pela foto panorâmica de 1956 ('As Fábricas coexistiram 3 - 1956.png'), a saudação ao Presidente Gronchi em 1958 ('Fabricas e coexistência...jpg'), os anúncios de Natal (1962 ID:1bcc, 1966 ID:cdc5, 1969 ID:6ac7) e a participação em curso de desenho industrial em 1967 ('Curso para desenhos - 1967.png')."
        },
        {
            "sub_section": "irmaos_panceri_ltda",
            "year": 1972,
            "title": "Modernização, Exportação e FENIT (Década de 1970)",
            "text": "Nos anos 70, a Panceri Ltda. adquiriu engomadeira automática e caldeira alemã. Exportou 4.000 dúzias de lenços para o Kuwait e importou fio especial. Em 1972, saudou os bancários. Em abril de 1973, foi escolhida pelo BRDE para a 16ª FENIT, onde apresentou Cetim Panceri, nylon e nova linha de acolchoados. Em agosto de 1973, recebeu teares 'Nissan Jet - Loom' do Japão para sua seção de acolchoaria.",
            "images": ["Curiosidade Panceri.jpg", "image.png", "image.png", "image.png"], # Panceri Dia Bancário 1972 (ID: 5adc), BRDE FENIT 1973 (ID: e0a7), Teares Nissan 1973 (ID: 6045)
            "corroboracao": "A significativa fase de modernização, expansão para exportação e participação em eventos de destaque da Tecelagem Panceri Ltda. na década de 1970 é corroborada por notícias sobre aquisição de maquinário e exportações ('Curiosidade Panceri.jpg'), a saudação ao Dia do Bancário em 1972 (ID: 5adc), a seleção para a FENIT em 1973 (ID: e0a7) e o recebimento de teares Nissan do Japão (ID: 6045)."
        },
        {
            "sub_section": "irmaos_panceri_ltda",
            "year": 1975,
            "title": "Participação na Festa da Uva e Fim do Setor Têxtil (1975, 1978-1981)",
            "text": "Em maio de 1975, a Tecelagem Panceri Ltda., com o Diretor Henrique Panceri, participou da Festa Nacional da Uva. No entanto, uma severa recessão econômica entre 1978 e 1981 levou ao fechamento do setor têxtil da empresa, desempregando mais de 30 funcionários.",
            "images": ["Panceri_Festa da Uva 03_1975.jpg", "221425a5-6116-4a75-843c-d4e11dd193a3.jpg", "Crise no setor Têxtil.jpg"],
            "corroboracao": "A participação da Tecelagem Panceri Ltda. na Festa da Uva de 1975 é documentada pela fotografia 'Panceri_Festa da Uva 03_1975.jpg'. O posterior encerramento de suas atividades têxteis, devido à crise econômica do final dos anos 70 e início dos 80, é reportado nos artigos de jornal '221425a5-6116-4a75-843c-d4e11dd193a3.jpg' e 'Crise no setor Têxtil.jpg'."
        }
    ],
    "pompeia": [
        {
            "year": 1908,
            "title": "Fundação da Tecelagem Nossa Senhora de Pompeia por Luiz Pizzamiglio (1908 / Pós-1917)",
            "text": "A Tecelagem Nossa Senhora de Pompeia tem seu início referenciado em 1908, associada a Luiz Pizzamiglio. Após seu casamento com Adelina Panceri (filha de Joseph Panceri) em 1917, Pizzamiglio assumiu e expandiu a tecelagem fundada por seu sogro em 1899 (que também fora denominada N.S. de Pompeia), consolidando-a. Adquiriu teares Jacquard mecânicos, impulsionando a produção.",
            "images": ["A trama dos fios - 1.jpg", "Pompeia 1 - 25_03_1950.png"],
            "corroboracao": "A consolidação da Tecelagem Nossa Senhora de Pompeia sob a direção de Luiz Pizzamiglio, após assumir a estrutura estabelecida por seu sogro Joseph Panceri, é documentada no artigo 'A Trama dos Fios' (imagem 'A trama dos fios - 1.jpg'). O anúncio de 1950 ('Pompeia 1 - 25_03_1950.png') celebra os 42 anos da empresa, corroborando sua fundação em 1908 e a liderança de Pizzamiglio."
        },
        {
            "year": 1928,
            "title": "Filosofia de Produção e Designer Olivério Tagliari (Década de 1920)",
            "text": "Luiz Pizzamiglio, também gerente da José Panceri & Cia. em 1929, focava a Tecelagem Pompeia na alta qualidade e exclusividade. Os desenhos e padrões eram criados por Olivério Tagliari. Tecidos de seda como um 'piqué mais grosso' para vestidos de noiva eram especialidade da casa. A fábrica é mencionada em um relato de visita à Panceri & Cia. em 1928.",
            "images": ["A trama dos fios - 2.jpg", "Relato de visita pompeia 1 - 1928.png", "Relato de visita pompeia 2 - 1928.png", "Relato de visita pompeia 3 - 1928.png"],
            "corroboracao": "O foco na alta qualidade e no design exclusivo da Tecelagem Pompeia, com Olivério Tagliari como criador dos padrões, é destacado no artigo 'A Trama dos Fios - 2.jpg'. Os relatos de visita de 1928 (imagens 'Relato de visita pompeia 1-3.png') confirmam a operação e a reputação da fábrica sob gestão de Luiz Pizzamiglio, que também atuava na Panceri & Cia."
        },
        {
            "year": 1950,
            "title": "Auge e Reconhecimento como 'Luiz Pizzamiglio & Filho' (1950)",
            "text": "Em 1950, o jornal 'O Pioneiro' celebrou os 42 anos (1908-1950) da Tecelagem de Seda N.S. de Pompeia. A empresa, então 'Luiz Pizzamiglio & Filho', era a 'tecnicamente melhor organizada fábrica de tecidos de seda', produzindo artigos finos para mercados nacionais e externos, com exposição na Rua Ernesto Alves, 1023.",
            "images": ["Pompeia 1 - 25_03_1950.png", "Pompeia 2 - 25_03_1950.png", "Pompeia 3 - 25_03_1950.png"],
            "corroboracao": "A celebração do 42º aniversário da Tecelagem N.S. de Pompeia em 1950, e seu reconhecimento como 'Luiz Pizzamiglio & Filho', uma das mais bem organizadas fábricas de seda, são documentados nas páginas do jornal 'O Pioneiro' ('Pompeia 1-3 - 25_03_1950.png'), que destacam sua produção e alcance de mercado."
        },
        {
            "year": 1956,
            "title": "Atividade Contínua e 'Vva. Luiz Pizzamiglio & Cia. Ltda.' (Década de 1950)",
            "text": "A empresa manteve atividade. Em 1937, 'Luiz Pizzamiglio & Cia.' era produtora de seda. Em ~1942, tinha 50 operários. Em 1956, a 'Tecelagem N.S. de Pompeia de Vva. Luiz Pizzamiglio & Cia. Ltda.' publicou uma mensagem de Natal. Em 1958, a 'Tecelagem Nossa Senhora de Pompeia' e 'Luiz Pizzamiglio & Fos.' (e 'Deposito de Fios Vva. Luiz Pizzamiglio & Cia. Ltda.') foram listadas em documentos.",
            "images": ["As Fábricas coexistiram 5 - 1937.png", "As Fábricas coexistiram 2 - 1942.png", "Pompeia existente em 1956.png", "Fabricas e coexistência - 13_09_1958.jpg", "As Fábricas coexistiram - 1958.png"],
            "corroboracao": "A continuidade das operações da Tecelagem Pompeia e a mudança de sua razão social para 'Vva. Luiz Pizzamiglio & Cia. Ltda.' após o falecimento de seu fundador são atestadas por diversas publicações: listagem como produtora de seda em 1937 ('As Fábricas coexistiram 5'), número de operários em 1942 ('As Fábricas coexistiram 2'), anúncio de Natal de 1956 ('Pompeia existente em 1956.png'), e menções em documentos de 1958 ('Fabricas e coexistência...jpg' e 'As Fábricas coexistiram - 1958.png')."
        },
        {
            "year": 1961,
            "title": "Falecimento de Luiz Pizzamiglio e Falência da Empresa (até 1961)",
            "text": "Luiz Pizzamiglio faleceu aos 58 anos (dia 20 do mês de publicação do obituário). Em 22 de agosto de 1961, foi publicado o aviso de Falência da 'Vva. Luiz Pizzamiglio & Filhos'. Em 14 de novembro de 1961, ocorreu a venda dos bens da massa falida. Os fichários da tecelagem foram conservados pela Scavino Bertuzzi.",
            "images": ["Falecimento Luiz Pizzamiglio.jpg", "7aa59d0e-d478-4c89-bc5c-31682a97b425.jpg", "Vva Luiz P.Falencia.22_08_1961.jpg", "image.png"], # ID: 9425231a... Edital Venda Bens
            "corroboracao": "O fim da trajetória da Tecelagem Pompeia é marcado pelo falecimento de seu fundador, Luiz Pizzamiglio, aos 58 anos (documentado em 'Falecimento Luiz Pizzamiglio.jpg' e no detalhe '7aa59d0e-d478-4c89-bc5c-31682a97b425.jpg'). Subsequentemente, o aviso de falência da 'Vva. Luiz Pizzamiglio & Filhos' foi publicado em 22/08/1961 ('Vva Luiz P.Falencia...jpg'), culminando com o edital de venda dos bens da massa falida em novembro de 1961 (referenciado como 'image.png' ID: 9425231a)."
        }
    ],
    "scavino": [ # Refere-se a Scavino & Bertuzzi
        {
            "year": 1917,
            "title": "Início de Manoel Scavino (1917-1922)",
            "text": "Em 1917, Manoel Scavino e sua esposa Ermelinda iniciaram atividades artesanais em Caxias, produzindo 'caronas' e 'ombreiras'. Em 1922, com capital acumulado, importou novos teares, expandindo a fábrica e diversificando para cobertores, capas e tecidos variados.",
            "images": ["Historia tecelagem em Museu.jpg"],
            "corroboracao": "Os primeiros passos de Manoel Scavino na indústria têxtil, desde a produção artesanal de 'caronas' e 'ombreiras' com sua esposa Ermelinda em 1917, até a primeira expansão de sua fábrica com teares importados em 1922 e a diversificação de produtos, são descritos no artigo 'Historia tecelagem em Museu.jpg'."
        },
        {
            "year": 1932,
            "title": "União Schio, Bertuzzi e Scavino para Colchas de Seda (1932)",
            "text": "Em 1932, as firmas Schio, Bertuzzi e Scavino (ou 'Scavina') uniram-se para fabricar colchas de seda. Inicialmente com teares manuais, a produção evoluiu com teares mecânicos para padrões mais sofisticados, incluindo motivos florais japoneses.",
            "images": ["Historia tecelagem em Museu.jpg", "As Fábricas coexistiram 5 - 1937.png"],
            "corroboracao": "A colaboração entre as firmas Schio, Bertuzzi e Scavino em 1932 para a fabricação de colchas de seda, e a evolução de teares manuais para mecânicos na busca por padrões mais sofisticados, é mencionada no artigo 'Historia tecelagem em Museu.jpg'. A listagem de produtores de 1937 ('As Fábricas coexistiram 5 - 1937.png') também referencia essa associação."
        },
        {
            "year": 1933,
            "title": "Fundação da Scavino & Bertuzzi e Primeiros Anos (1933)",
            "text": "A Scavino & Bertuzzi foi fundada em 23 de agosto de 1933 por Alexandre Scavino, Luiz 'Bórtolo' Bertuzzi, César Scavino, e outros, incluindo Angelo Scavino (pai), responsável pelos desenhos. Produziam sedas para camisas, artigos de luto, bandeiras e indumentárias eclesiásticas, usando teares manuais (alguns de Joseph Panceri) e importados.",
            "images": ["A trama dos fios - 2.jpg", "Scavino comemora seus 55 anos - 1988.jpg"],
            "corroboracao": "Detalhes sobre a fundação da Scavino & Bertuzzi em 23 de agosto de 1933, seus sócios fundadores (Alexandre Scavino, Luiz 'Bórtolo' Bertuzzi, César Scavino, Angelo Scavino), os produtos iniciais como sedas, artigos de luto e indumentárias eclesiásticas, e o uso de teares manuais (alguns originários de Joseph Panceri) e importados, são corroborados pelo artigo 'A trama dos fios - 2.jpg' e pelo artigo comemorativo de 55 anos da empresa ('Scavino comemora seus 55 anos - 1988.jpg')."
        },
        {
            "year": 1958,
            "title": "Atividade Contínua, Designers e Desafios (1958, ~1980)",
            "text": "Em 1958, 'Scavino Bertuzzi & Cia.' e 'Fabrica de Tecidos e Artefatos de Rayon Scavino Bertuzzi & Cia.' são listadas em documentos. Um artigo de ~1980 retrata a empresa ainda usando teares manuais antigos, com Ulysses Menegalli e posteriormente Idalino Pizzamiglio (não o Luiz da Pompeia) como criadores dos desenhos. Enfrentavam custos de modernização e falta de mão de obra qualificada. Produziam 17-18 mil metros/mês com 48 empregados (seda, poliéster, algodão, artigos gauchescos).",
            "images": ["As Fábricas coexistiram - 1958.png", "Fabricas e coexistência - 13_09_1958.jpg", "A trama dos fios - 2.jpg"],
            "corroboracao": "A operação contínua da Scavino & Bertuzzi é evidenciada por sua listagem em documentos de 1958 ('As Fábricas coexistiram - 1958.png', 'Fabricas e coexistência...jpg'). O artigo 'A trama dos fios - 2.jpg' (circa 1980) descreve a manutenção de teares manuais, a atuação dos designers Ulysses Menegalli e Idalino Pizzamiglio, os desafios de modernização e a capacidade produtiva da empresa na época."
        },
        {
            "year": 1982,
            "title": "Foco na Tradição Gaúcha e 55 Anos (1982, 1988)",
            "text": "Em 1982, um anúncio destacava a produção de 'lenços e palas para a tradição gaúcha' em rayon. Em 1988, celebrando 55 anos, a empresa utilizava teares Raschel para faixas (inclusive militares) e teares suíços para etiquetas. Nelly Scavino Boff é mencionada.",
            "images": ["image.png", "Scavino comemora seus 55 anos - 1988.jpg"], # ID: bbff5247... Anúncio Tradição Gaúcha
            "corroboracao": "A especialização da Scavino & Bertuzzi em produtos regionais como lenços e palas é destacada no anúncio de 1982 ('image.png' ID: bbff...). O artigo de 1988 ('Scavino comemora seus 55 anos - 1988.jpg') celebra os 55 anos da empresa, mencionando o uso de teares Raschel e suíços, e a figura de Nelly Scavino Boff na gestão."
        },
        {
            "year": 1965,
            "title": "Legado e Continuidade Pós-Crise dos Anos 60",
            "text": "Após a crise das fibras sintéticas nos anos 60, que levou muitas tecelagens à falência, a Scavino-Bertuzzi, junto com o Lanifício Sehbe, destacavam-se como as que ainda operavam em plena capacidade, demonstrando resiliência.",
            "images": ["Historia tecelagem em Museu.jpg"],
            "corroboracao": "A resiliência e a continuidade operacional da Tecelagem Scavino-Bertuzzi, que se destacou ao lado do Lanifício Sehbe por manter plena capacidade produtiva após a severa crise das fibras sintéticas na década de 1960 (um período que resultou na falência de muitas outras tecelagens), são ressaltadas no artigo 'Historia tecelagem em Museu.jpg'."
        }
    ],
# --- DENTRO DE initial_data_to_seed NO SEU app.py ---
    "gallery_images": [
        {"chronological_order": 1, "fileName": "9e02599a-823a-484c-a647-8e8205610d38.jpg", "title": "Família Panceri na 6ª Légua (Final Séc. XIX)", "corroboration": "Registro fotográfico da família Panceri, datado do final do século XIX, em sua primeira propriedade na localidade da 6ª Légua. Esta imagem documenta o período inicial da família em Caxias do Sul, dedicado à agricultura, antes do retorno de Joseph Panceri às atividades de tecelagem.", "admin_assigned_section": "Panceri", "tags": "família Panceri,Joseph Panceri,6ª Légua,século XIX,pioneirismo,agricultura,fotografia"},
        {"chronological_order": 2, "fileName": "Giussepe a procura de casulo, representante EBERLE - 1909.png", "title": "Anúncio Giuseppe Panceri - Compra de Casulos (1909)", "corroboration": "Recorte de anúncio em italiano, veiculado em 1909, pela 'Fabbrica di tessuti di seta di GIUSEPPE PANCIERI - Caxias'. O informe público visava a compra de casulos de seda e indicava a prestigiosa firma Abramo Eberle & C. como seus representantes comerciais para esta transação, evidenciando as primeiras parcerias industriais de Panceri.", "admin_assigned_section": "Panceri", "tags": "Giuseppe Panceri,Abramo Eberle,anúncio,seda,casulos,1909"},
        {"chronological_order": 3, "fileName": "Historia Panceri 1 - 1910.png", "title": "Relato Fábrica de José Panceri - Parte 1 (1910)", "corroboration": "Primeira parte de um artigo de jornal publicado em 1910, que relata uma visita à pioneira fábrica de tecidos de seda de José Panceri. O texto detalha os teares em operação na época e os desafios enfrentados pelo industrial na obtenção de matéria-prima essencial para sua produção de alta qualidade.", "admin_assigned_section": "Panceri", "tags": "José Panceri,fábrica,artigo de jornal,seda,1910"},
        {"chronological_order": 4, "fileName": "Historia Panceri 2 - 1910.png", "title": "Relato Fábrica de José Panceri - Parte 2 (1910)", "corroboration": "Continuação do artigo de jornal de 1910 sobre a fábrica de José Panceri. Nesta seção, o jornalista discute a superior qualidade da seda produzida localmente por Panceri e enfatiza a premente necessidade de incentivo à sericicultura na região de Caxias do Sul para suprir a demanda crescente por seus tecidos.", "admin_assigned_section": "Panceri", "tags": "José Panceri,fábrica,artigo de jornal,seda,1910,sericicultura"},
        {"chronological_order": 5, "fileName": "A ligação entre Panceri e Eberle, dentro e fora dos comércios.png", "title": "Sociedade Recreio Dante (Panceri e Eberle, ~1910s)", "corroboration": "Documento da Sociedade Recreio Dante, referente à década de 1910, que lista José Panceri como presidente e Abramo Eberle como tesoureiro. Ilustra o envolvimento e a colaboração dos proeminentes industriais na vida comunitária e social de Caxias do Sul, além de suas atividades comerciais.", "admin_assigned_section": "Panceri", "tags": "Sociedade Recreio Dante,José Panceri,Abramo Eberle,documento,década de 1910,comunidade"},
        {"chronological_order": 6, "fileName": "Doação Fábrica Panceri - 1917 por Giussepe Panceri.jpg", "title": "Doação Palla de Seda Panceri ao Cônsul Uruguaio (1917)", "corroboration": "Recorte de notícia de jornal de 1917, reportando que um 'fino pala de sêda', produto de reconhecida qualidade da fábrica de José Panceri, foi ofertado como um presente de prestígio ao então cônsul geral do Uruguai. Este gesto destaca o reconhecimento e a valorização dos artefatos produzidos pela tecelagem Panceri.", "admin_assigned_section": "Panceri", "tags": "José Panceri,doação,pala de seda,1917,artigo de jornal,produto"},
        {"chronological_order": 7, "fileName": "Visita Panceri - 1921.png", "title": "Visita à Fábrica José Panceri & Cia. - Parte 1 (1921)", "corroboration": "Relato de visita publicado em 1921, detalhando as instalações e operações da fábrica de José Panceri & Cia., que já se encontrava estabelecida há mais de uma década e em processo de expansão de suas atividades na produção de seda.", "admin_assigned_section": "Panceri", "tags": "José Panceri & Cia,artigo de jornal,visita à fábrica,1921"},
        {"chronological_order": 8, "fileName": "Visita Panceri 2 - 1921.png", "title": "Visita à Fábrica José Panceri & Cia. - Parte 2 (1921)", "corroboration": "Continuação do relato de visita à fábrica José Panceri & Cia. em 1921. Esta parte do artigo menciona os sócios envolvidos na empresa, incluindo o próprio José Panceri, seus filhos, e Luiz Pizzamiglio, que teria um papel fundamental na futura Tecelagem Pompeia.", "admin_assigned_section": "Panceri", "tags": "José Panceri & Cia,artigo de jornal,Luiz Pizzamiglio,1921"},
        {"chronological_order": 9, "fileName": "Doação Fábrica Panceri - 1921 por Giussepe Panceri2.jpg", "title": "Doação Palla Panceri & Cia. ao Pres. Borges de Medeiros (1921)", "corroboration": "Notícia de jornal de 1921 que reporta a doação de um 'custoso palla de seda', produzido pela fábrica Josè Panceri & Cia., ao então Presidente do Estado do Rio Grande do Sul, Borges de Medeiros, evidenciando o prestígio dos produtos da tecelagem.", "admin_assigned_section": "Panceri", "tags": "José Panceri & Cia,doação,pala de seda,Borges de Medeiros,1921,artigo de jornal"},
        {"chronological_order": 10, "fileName": "Relato de visita pompeia 1 - 1928.png", "title": "Visita à Panceri & Cia (Pompeia) - Parte 1 (1928)", "corroboration": "Primeira parte de um relato de visita, publicado em 1928, à fábrica de seda Panceri & Cia. Neste período, a unidade era gerenciada por Luiz Pizzamiglio e é associada à origem da futura Tecelagem Pompeia, já demonstrando sua capacidade produtiva e foco na seda.", "admin_assigned_section": "Pompeia", "tags": "Panceri & Cia,Luiz Pizzamiglio,Tecelagem Pompeia,artigo de jornal,1928"},
        {"chronological_order": 11, "fileName": "Relato de visita pompeia 2 - 1928.png", "title": "Visita à Panceri & Cia (Pompeia) - Parte 2 (1928)", "corroboration": "Continuação do detalhado relato de 1928 sobre a visita à Panceri & Cia (que viria a ser a Tecelagem Pompeia), descrevendo os teares em funcionamento, a organização da produção e a variedade de produtos de seda que já eram confeccionados pela empresa de Luiz Pizzamiglio.", "admin_assigned_section": "Pompeia", "tags": "Panceri & Cia,Tecelagem Pompeia,artigo de jornal,teares,1928"},
        {"chronological_order": 12, "fileName": "Relato de visita pompeia 3 - 1928.png", "title": "Visita à Panceri & Cia (Pompeia) - Parte 3 (1928)", "corroboration": "Conclusão do relato de visita de 1928 à Panceri & Cia (futura Tecelagem Pompeia). O jornalista menciona o fundador original da estrutura, José Panceri (pai), e destaca a grande demanda e aceitação que os artigos de seda da fábrica, sob gestão de Luiz Pizzamiglio, já possuíam no mercado.", "admin_assigned_section": "Pompeia", "tags": "Panceri & Cia,Tecelagem Pompeia,José Panceri,artigo de jornal,1928"},
        {"chronological_order": 13, "fileName": "Relato panceri - 20_09_1929.png", "title": "Modernização Irmãos Panceri com Tear Francês (1929)", "corroboration": "Notícia de jornal, datada de 20 de setembro de 1929, informando que a firma Irmãos Panceri estava modernizando seu parque fabril com a aquisição de um novo e moderno tear importado da França, movido a eletricidade, um avanço para a época.", "admin_assigned_section": "Panceri", "tags": "Irmãos Panceri,modernização,teares,1929,artigo de jornal"},
        {"chronological_order": 14, "fileName": "Relato panceri 1 - 12_09_1929.png", "title": "Visita à Panceri & Cia. em Crise - Parte 1 (1929)", "corroboration": "Início de um relato de visita à fábrica de seda Panceri & Cia., então gerida por Luiz Pizzamiglio, em 12 de setembro de 1929. O artigo destaca o progresso industrial da unidade apesar do contexto de crise econômica que afetava o país.", "admin_assigned_section": "Panceri", "tags": "Panceri & Cia,Luiz Pizzamiglio,artigo de jornal,crise econômica,1929"},
        {"chronological_order": 15, "fileName": "Relato panceri 2 - 12_09_1929.png", "title": "Visita à Panceri & Cia. - Teares e Produtos (1929)", "corroboration": "Detalhes sobre os 32 teares (dos quais 5 eram elétricos) em operação na Panceri & Cia. em 1929, e a variedade de produtos de seda de alta qualidade confeccionados pela empresa, conforme relato de visita jornalística.", "admin_assigned_section": "Panceri", "tags": "Panceri & Cia,teares,produtos de seda,1929,artigo de jornal"},
        {"chronological_order": 16, "fileName": "Relato panceri 3 - 12_09_1929.png", "title": "Visita à Panceri & Cia. - Qualidade e Técnico (1929)", "corroboration": "Menção a Antonio Ferle, descrito como um competente técnico da fábrica Panceri & Cia., e um elogio à alta qualidade dos tecidos produzidos pela empresa em 1929, mesmo durante um período de crise econômica.", "admin_assigned_section": "Panceri", "tags": "Panceri & Cia,qualidade,Antonio Ferle,1929,artigo de jornal"},
        {"chronological_order": 17, "fileName": "Relato panceri 4 - 12_09_1929.png", "title": "Visita à Panceri & Cia. - Agradecimentos (1929)", "corroboration": "Conclusão do relato de visita à Panceri & Cia. em 1929, com agradecimentos direcionados a Luiz Pizzamiglio, então gerente da fábrica, pela recepção e informações prestadas ao jornalista.", "admin_assigned_section": "Panceri", "tags": "Panceri & Cia,Luiz Pizzamiglio,1929,artigo de jornal"},
        {"chronological_order": 18, "fileName": "image.png", "title": "Artigo Irmãos Panceri (ID: 97a0)", "corroboration": "Artigo publicado em uma edição especial do jornal 'O CAXIAS' (circa década de 1930), destacando a fábrica de tecidos de seda dos Irmãos Panceri e elogiando a qualidade superior de seus produtos.", "admin_assigned_section": "Panceri", "tags": "Irmãos Panceri,artigo de jornal,O CAXIAS,seda,década de 1930"},
        {"chronological_order": 19, "fileName": "As Fábricas coexistiram 4 - 1931.png", "title": "Reclamação sobre Guias de Exportação (1931)", "corroboration": "Artigo de jornal de 1931 que critica a exigência de guias de exportação para produtos nacionais, mencionando as firmas Panceri & Cia e Irmãos Panceri entre as empresas exportadoras da região afetadas pela burocracia.", "admin_assigned_section": "Geral", "tags": "Panceri & Cia,Irmãos Panceri,exportação,1931,artigo de jornal,burocracia"},
        {"chronological_order": 20, "fileName": "As Fábricas coexistiram 5 - 1937.png", "title": "Produtores de Tecidos de Seda em Caxias (1937)", "corroboration": "Lista extraída de publicação de 1937, enumerando os produtores de tecidos de seda estabelecidos em Caxias do Sul. Entre eles, destacam-se Luiz Pizzamiglio & Cia. (Pompeia), Irmãos Panceri, e a união Schio, Bertuzzi & Scavina.", "admin_assigned_section": "Geral", "tags": "produtores de seda,1937,Pizzamiglio,Panceri,Scavino,Bertuzzi,documento,indústria"},
        {"chronological_order": 21, "fileName": "As Fábricas coexistiram 2 - 1942.png", "title": "Lista de Indústrias e Operários (~1942)", "corroboration": "Documento ou publicação (circa 1942) contendo uma lista de indústrias de Caxias do Sul e o respectivo número de operários. A Tecelagem N.S. de Pompeia (Luiz Pizzamiglio) figura com 50 operários, enquanto a Irmãos Panceri possuía 30.", "admin_assigned_section": "Geral", "tags": "indústrias,operários,1942,Pompeia,Panceri,documento,estatísticas"},
        {"chronological_order": 22, "fileName": "Giuseppe e o inicio dos irmaos panceri.png", "title": "José Panceri (1858-1943) e Irmãos Panceri", "corroboration": "Montagem com fotografia de José Panceri e uma breve nota biográfica, ressaltando seu pioneirismo na indústria da seda em Caxias. Menciona a continuidade da tradição familiar por seus filhos, José e Agostinho, através da firma Irmãos Panceri, estabelecida em 1928.", "admin_assigned_section": "Panceri", "tags": "José Panceri,Irmãos Panceri,biografia,fotografia,pioneirismo"},
        {"chronological_order": 23, "fileName": "Pompeia 1 - 25_03_1950.png", "title": "Anúncio Tecelagem Pompeia - 42 Anos (1950)", "corroboration": "Página comemorativa do jornal 'O Pioneiro', de 25 de março de 1950, celebrando os 42 anos de fundação (1908-1950) da Tecelagem de Seda Nossa Senhora de Pompeia. A matéria destaca seu titular, Luiz Pizzamiglio.", "admin_assigned_section": "Pompeia", "tags": "Tecelagem Pompeia,Luiz Pizzamiglio,aniversário,1950,O Pioneiro,artigo de jornal"},
        {"chronological_order": 24, "fileName": "Pompeia 2 - 25_03_1950.png", "title": "Vista Fabril da Tecelagem Pompeia (1950)", "corroboration": "Fotografia exibindo o conjunto fabril da Tecelagem Nossa Senhora de Pompeia em 1950. Esta imagem fazia parte do anúncio comemorativo de 42 anos da empresa, publicado no jornal 'O Pioneiro'.", "admin_assigned_section": "Pompeia", "tags": "Tecelagem Pompeia,fábrica,1950,fotografia,arquitetura industrial"},
        {"chronological_order": 25, "fileName": "Pompeia 3 - 25_03_1950.png", "title": "Interior da Fábrica Pompeia - L. Pizzamiglio & Filho (1950)", "corroboration": "Registro fotográfico do interior de uma seção da Tecelagem Luiz Pizzamiglio & Filho (Pompeia) em 1950, mostrando os teares em plena operação. Publicada no anúncio de aniversário da empresa.", "admin_assigned_section": "Pompeia", "tags": "Tecelagem Pompeia,Luiz Pizzamiglio & Filho,fábrica,teares,1950,fotografia,maquinário"},
        {"chronological_order": 26, "fileName": "Stand Irmaos Panceri - 1950.png", "title": "Stand Irmãos Panceri - Festa da Uva (1950)", "corroboration": "Fotografia do stand da Firma Irmãos Panceri durante a Festa da Uva de Caxias do Sul em 1950. O espaço expositivo da tecelagem foi reconhecido com medalha de ouro pela qualidade de seus produtos. O artista Paulo Gazzo é visto no interior.", "admin_assigned_section": "Panceri", "tags": "Irmãos Panceri,Festa da Uva,1950,stand,evento,prêmio"},
        {"chronological_order": 27, "fileName": "As Fábricas coexistiram 3 - 1956.png", "title": "Vista Parcial de Caxias - Indústrias (1956)", "corroboration": "Foto panorâmica de Caxias do Sul em 1956, destacando as chaminés e estruturas de diversas indústrias, entre elas a Tecelagem N.S. da Pompeia (de Pizzamiglio) e a Tecelagem Panceri, mostrando a paisagem industrial da época.", "admin_assigned_section": "Geral", "tags": "Caxias do Sul,vista panorâmica,indústria,1956,Pompeia,Panceri,fotografia"},
        {"chronological_order": 28, "fileName": "Pompeia existente em 1956.png", "title": "Anúncio de Natal Tecelagem Pompeia (1956)", "corroboration": "Anúncio publicitário com mensagem de Natal e Ano Novo da Tecelagem N.S. de Pompeia, sob a razão social 'Vva. Luiz Pizzamiglio & Cia. Ltda.'. Publicado no Natal de 1956, indica a continuidade das atividades da empresa após o falecimento de Luiz Pizzamiglio.", "admin_assigned_section": "Pompeia", "tags": "Tecelagem Pompeia,Vva. Luiz Pizzamiglio,anúncio,Natal,1956"},
        {"chronological_order": 29, "fileName": "Fabricas e coexistência - 13_09_1958.jpg", "title": "Saudação Indústrias Têxteis ao Pres. Gronchi (1958)", "corroboration": "Página de jornal de 13 de setembro de 1958, com uma saudação do Sindicato da Indústria de Fiação e Tecelagem de Caxias do Sul ao Presidente da Itália, Giovanni Gronchi, por ocasião de sua visita. Lista importantes empresas do setor, incluindo Tecelagem Panceri Ltda., Tecelagem Nossa Senhora de Pompeia, e Fabrica de Tecidos e Artefatos de Rayon Scavino Bertuzzi & Cia.", "admin_assigned_section": "Geral", "tags": "indústria têxtil,sindicato,Presidente Gronchi,1958,Panceri,Pompeia,Scavino & Bertuzzi,artigo de jornal,homenagem"},
        {"chronological_order": 30, "fileName": "As Fábricas coexistiram - 1958.png", "title": "Edital Sindicato Trabalhadores Têxteis (1958)", "corroboration": "Edital datado de 27 de dezembro de 1958, emitido pelo Sindicato dos Trabalhadores na Indústria de Fiação e Tecelagem de Caxias do Sul. Convoca para eleição e lista locais de votação, incluindo as firmas Luiz Pizzamiglio & Fos., Irmãos Panceri, e Scavino Bertuzzi & Cia.", "admin_assigned_section": "Geral", "tags": "sindicato dos trabalhadores,eleição,1958,Pizzamiglio,Panceri,Scavino & Bertuzzi,documento,edital"},
        {"chronological_order": 31, "fileName": "Falecimento Luiz Pizzamiglio.jpg", "title": "Obituário de Luiz Pizzamiglio", "corroboration": "Nota de falecimento do industrialista Luiz Pizzamiglio, figura proeminente e diretor da Tecelagem de Seda Nossa Senhora Pompeia. Ocorrido aos 58 anos, seu passamento foi noticiado como uma grande perda para a indústria local (data exata da publicação não visível, mas anterior a agosto de 1961).", "admin_assigned_section": "Pompeia", "tags": "Luiz Pizzamiglio,falecimento,obituário,Tecelagem Pompeia"},
        {"chronological_order": 32, "fileName": "7aa59d0e-d478-4c89-bc5c-31682a97b425.jpg", "title": "Falecimento Luiz Pizzamiglio (Detalhe Idade)", "corroboration": "Fragmento de um obituário que menciona a idade de Luiz Pizzamiglio ao falecer: 58 anos. Confirma a informação do registro principal de seu falecimento.", "admin_assigned_section": "Pompeia", "tags": "Luiz Pizzamiglio,falecimento,obituário,idade"},
        {"chronological_order": 33, "fileName": "Vva Luiz P.Falencia.22_08_1961.jpg", "title": "Aviso de Falência Vva. Luiz Pizzamiglio (1961)", "corroboration": "Comunicação oficial, publicada em jornal em 22 de agosto de 1961, informando a declaração de falência da empresa 'Vva. Luiz Pizzamiglio & Cia. Ltda.', que operava a Tecelagem Pompeia.", "admin_assigned_section": "Pompeia", "tags": "Vva. Luiz Pizzamiglio,Tecelagem Pompeia,falência,1961,documento oficial,artigo de jornal"},
        {"chronological_order": 34, "fileName": "image.png", "title": "Edital Venda Bens Falida Vva. L. Pizzamiglio (ID: 9425)", "corroboration": "Edital de Concorrência para a venda dos bens pertencentes à Massa Falida de Vva. Luiz Pizzamiglio & Cia. Ltda. (Tecelagem Pompeia). As propostas foram aceitas até 13 de novembro de 1961, com abertura no dia seguinte.", "admin_assigned_section": "Pompeia", "tags": "Vva. Luiz Pizzamiglio,Tecelagem Pompeia,falência,venda de bens,edital,1961,documento"},
        {"chronological_order": 35, "fileName": "image.png", "title": "Tecelagem Panceri Ltda. - Natal (1962) (ID: 1bcc)", "corroboration": "Anúncio de saudação de Natal de 1962, publicado pela Tecelagem Panceri Ltda. Faz parte de uma página coletiva de saudações de diversas empresas de Caxias do Sul à comunidade.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,Natal,1962,publicidade,anúncio"},
        {"chronological_order": 36, "fileName": "image.png", "title": "Tecelagem Panceri Ltda. - Natal (1966) (ID: cdc5)", "corroboration": "Publicidade da Tecelagem Panceri Limitada, desejando Feliz Natal em 1966. O anúncio menciona a produção de 'Tecidos e Artefatos de Seda e Naylon' e o endereço na Rua Vereador Mário Pezzi, 458.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,Natal,1966,publicidade,seda,nylon,anúncio"},
        {"chronological_order": 37, "fileName": "Curso para desenhos - 1967.png", "title": "Tecelagem Panceri em Curso de Desenho (1967)", "corroboration": "Notícia de jornal de 1967 sobre a participação da Tecelagem Panceri em um Curso Prático de Cores para Desenho Industrial. O curso foi patrocinado pelo Centro da Indústria Fabril em colaboração com o SENAI, visando o aprimoramento técnico.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,curso,desenho industrial,SENAI,1967,capacitação,artigo de jornal"},
        {"chronological_order": 38, "fileName": "image.png", "title": "Tecelagem Panceri Ltda. - Natal (1969) (ID: 6ac7)", "corroboration": "Anúncio de saudação natalina da Tecelagem Panceri Limitada, datado de 1969. Reitera os produtos (Seda, Raion e Nylon) e o endereço da empresa, similar a anúncios anteriores.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,Natal,1969,publicidade,anúncio"},
        {"chronological_order": 39, "fileName": "image.png", "title": "Tecelagem Panceri - Dia do Bancário (1972) (ID: 5adc)", "corroboration": "Anúncio da Tecelagem Panceri Ltda., publicado em 26 de agosto de 1972, em saudação ao Dia Nacional do Bancário. Detalha seus produtos principais: Seda, Raion e Estamparia, e o endereço da fábrica.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,Dia do Bancário,1972,publicidade,seda,raion,estamparia"},
        {"chronological_order": 40, "fileName": "image.png", "title": "Tecelagem Panceri na FENIT (1973) (ID: e0a7)", "corroboration": "Notícia de abril de 1973 informando que o Banco Regional de Desenvolvimento do Extremo Sul (BRDE) e o Governo do Estado do Rio Grande do Sul selecionaram a Tecelagem Panceri Ltda. para representar a indústria gaúcha na 16ª FENIT (Feira Nacional da Indústria Têxtil) em São Paulo.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,BRDE,FENIT,1973,feira têxtil,evento,artigo de jornal"},
        {"chronological_order": 41, "fileName": "image.png", "title": "Tecelagem Panceri Recebe Teares Nissan (1973) (ID: 6045)", "corroboration": "Reportagem de 4 de agosto de 1973 sobre a Tecelagem Panceri Ltda. e a aquisição de modernos teares 'Nissan Jet Loom', importados do Japão. Estes equipamentos, considerados os mais avançados na época, foram destinados à seção de acolchoaria da empresa, representando um grande investimento em modernização.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,teares Nissan,modernização,1973,acolchoaria,importação,artigo de jornal,maquinário"},
        {"chronological_order": 42, "fileName": "b3a708bc-094f-4d7a-b3bf-348880676c79.jpg", "title": "Anúncio FENIT", "corroboration": "Anúncio institucional da FENIT (Feira Nacional da Indústria Têxtil), destacando sua 16ª edição (2 a 10 de junho) como um evento fechado, direcionado a profissionais e compradores do setor têxtil nacional e internacional.", "admin_assigned_section": "Geral", "tags": "FENIT,feira têxtil,anúncio,publicidade,indústria têxtil"},
        {"chronological_order": 43, "fileName": "Panceri_Festa da Uva 03_1975.jpg", "title": "Tecelagem Panceri na Festa da Uva (1975)", "corroboration": "Registro fotográfico da participação da Tecelagem Panceri Ltda. na Festa Nacional da Uva de 1975. Na imagem, o Diretor Sr. Henrique Panceri recepciona o Dr. Dinar Gigante, representante do Banco do Brasil, no estande da empresa, demonstrando a presença da tecelagem nos grandes eventos locais.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,Festa da Uva,Henrique Panceri,1975,evento,fotografia"},
        {"chronological_order": 44, "fileName": "Crise no setor Têxtil.jpg", "title": "Crise Têxtil e Fechamento Panceri (Pós-1978)", "corroboration": "Artigo de jornal (publicado após 1978) que discute a severa crise enfrentada pelo setor têxtil em Caxias do Sul. O presidente do Sindicato dos Trabalhadores, Renato Viero, menciona o fechamento do setor de tecelagem da Panceri, resultando no desemprego de mais de 30 funcionários. O empresário Miguel Sehbe também comenta a difícil situação da indústria.", "admin_assigned_section": "Panceri", "tags": "crise têxtil,Panceri,fechamento,anos 70,artigo de jornal,economia,sindicato"},
        {"chronological_order": 45, "fileName": "221425a5-6116-4a75-843c-d4e11dd193a3.jpg", "title": "Retrocessão Setor Têxtil e Panceri (Pós-1978)", "corroboration": "Artigo de jornal sobre a 'violenta recessão' que atingiu o setor de malharias e tecelagens a partir de 1978, com seu auge em 1981. O texto cita explicitamente o fechamento de empresas tradicionais como a Tecelagem Panceri como consequência direta deste cenário econômico adverso para a indústria local.", "admin_assigned_section": "Panceri", "tags": "recessão econômica,setor têxtil,Panceri,fechamento,anos 70,anos 80,artigo de jornal"},
        {"chronological_order": 46, "fileName": "image.png", "title": "Anúncio Scavino & Bertuzzi - Tradição Gaúcha (ID: bbff)", "corroboration": "Anúncio da Scavino, Bertuzzi & Cia. Ltda., provavelmente da década de 1980 (inferido pelo uso de CEP e DDD). A publicidade destaca a produção especializada da tecelagem em artigos de Rayon voltados para a tradição gaúcha, como lenços e palas.", "admin_assigned_section": "Scavino & Bertuzzi", "tags": "Scavino & Bertuzzi,tradição gaúcha,rayon,lenços,palas,anos 80,publicidade"},
        {"chronological_order": 47, "fileName": "Scavino comemora seus 55 anos - 1988.jpg", "title": "Scavino & Bertuzzi - 55 Anos (1988)", "corroboration": "Artigo de jornal publicado em 1988, comemorando os 55 anos de fundação da Tecelagem Scavino & Bertuzzi (fundada em 24 de agosto de 1933). A matéria detalha a rica história da empresa, sua evolução ao longo das décadas, a diversificada linha de produtos e presta homenagem a funcionários de longa data como Zelia Costamilan e Leonidas Zambiassi.", "admin_assigned_section": "Scavino & Bertuzzi", "tags": "Scavino & Bertuzzi,aniversário,1988,história,artigo de jornal,fundação 1933,comemoração"},
        {"chronological_order": 48, "fileName": "A trama dos fios - 1.jpg", "title": "Artigo 'A trama dos fios' - Pág 1 (1988)", "corroboration": "Primeira página do extenso artigo 'MEMÓRIA - A trama dos fios', publicado pelo Jornal de Caxias (Pioneiro) em 18 de janeiro de 1988. Este documento é uma fonte primária crucial para o resumo histórico das tecelagens Panceri, Pizzamiglio (Tecelagem Pompeia) e Scavino Bertuzzi.", "admin_assigned_section": "Geral", "tags": "A Trama dos Fios,artigo de jornal,Pioneiro,1988,história,Panceri,Pompeia,Scavino & Bertuzzi"},
        {"chronological_order": 49, "fileName": "A trama dos fios - 2.jpg", "title": "Artigo 'A trama dos fios' - Pág 2 (1988)", "corroboration": "Segunda página do artigo 'MEMÓRIA - A trama dos fios' (Jornal de Caxias, 18/01/1988), continuando a narrativa sobre a Tecelagem Scavino Bertuzzi, detalhando os tipos de tecidos produzidos, a mão de obra empregada e os desafios enfrentados pela indústria na época.", "admin_assigned_section": "Scavino & Bertuzzi", "tags": "A Trama dos Fios,artigo de jornal,Pioneiro,1988,Scavino & Bertuzzi,tecidos"},
        {"chronological_order": 50, "fileName": "Fabricas3.jpg", "title": "Artigo 'História da tecelagem em mostra no Museu' (1988)", "corroboration": "Terceira página do artigo 'MEMÓRIA - A trama dos fios' (Jornal de Caxias, 18/01/1988), também identificada como 'Historia tecelagem em Museu.jpg'. Descreve uma exposição no Museu e Arquivo Histórico Municipal sobre a tecelagem em Caxias, mencionando pioneiros e a crise das fibras sintéticas nos anos 60.", "admin_assigned_section": "Geral", "tags": "A Trama dos Fios,artigo de jornal,Pioneiro,1988,museu,exposição,história da tecelagem,crise"},
        {"chronological_order": 51, "fileName": "Historia tecelagem em Museu.jpg", "title": "História da Tecelagem em Mostra no Museu", "corroboration": "Artigo de jornal sobre uma exposição realizada no Museu Municipal de Caxias do Sul, detalhando a história da tecelagem na cidade. Destaca pioneiros como José Panceri e Manoel Scavino, e o impacto de eventos como a crise das fibras sintéticas na década de 1960. (Conteúdo idêntico a Fabricas3.jpg).", "admin_assigned_section": "Geral", "tags": "museu,exposição,história da tecelagem,José Panceri,Manoel Scavino,artigo de jornal"},
        {"chronological_order": 52, "fileName": "image.png", "title": "Tecelagem Panceri Ltda. - Lista (ID: 6a89)", "corroboration": "Fragmento de uma lista de empresas (sem data clara, mas referente ao período de atividade da Panceri Ltda.), onde a 'Tecelagem Panceri Ltda.' aparece associada ao número 92, possivelmente indicando o número de funcionários ou uma ordem em um ranking industrial da época.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,lista de empresas,documento,indústria"},
        {"chronological_order": 53, "fileName": "image.png", "title": "Anúncio Tecelagem Panceri (ID: 4008)", "corroboration": "Anúncio da Tecelagem Panceri Ltda. (sem data explícita, mas de seu período de atividade) destacando a produção de 'Tecidos e Artefatos de Seda e Raion'. Informa o endereço na Rua Vereador Mário Pezzi, 458, e o telefone 2261.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,anúncio,publicidade,seda,raion,endereço"},
        {"chronological_order": 54, "fileName": "Curiosidade Panceri.jpg", "title": "Tecelagem Panceri - Investimentos e Exportações", "corroboration": "Notícia de jornal (sem data explícita, mas provavelmente da década de 1970) detalhando investimentos da Tecelagem Panceri Ltda., como a aquisição de uma engomadeira automática e uma caldeira alemã. Também menciona planos de exportação de lenços para o Kuwait e importação de fio especial para tecidos de estamparia.", "admin_assigned_section": "Panceri", "tags": "Tecelagem Panceri,investimento,exportação,Kuwait,maquinário,engomadeira,caldeira,anos 70,artigo de jornal"},
        {"chronological_order": 55, "fileName": "História familia Panceri 1.jpg", "title": "História Família Panceri - Parte 1", "corroboration": "Primeira página de um texto datilografado que narra a história detalhada da família Panceri. Cobre desde as origens da família na Itália, a decisão de emigração de Joseph Panceri, e os primeiros anos de estabelecimento no Brasil, na região de Caxias do Sul.", "admin_assigned_section": "Panceri", "tags": "família Panceri,história,Itália,emigração,Joseph Panceri,documento datilografado"},
        {"chronological_order": 56, "fileName": "Historia familia Panceri 2.jpg", "title": "História Família Panceri - Parte 2", "corroboration": "Segunda página do documento datilografado sobre a história da família Panceri. Detalha a vida da família na localidade da 6ª Légua, a engenhosa produção inicial de 'sobre-chincha' por Joseph Panceri, os desafios familiares enfrentados, incluindo lutos, e o segundo casamento de Joseph.", "admin_assigned_section": "Panceri", "tags": "família Panceri,história,6ª Légua,produção artesanal,sobre-chincha,documento datilografado"},
        {"chronological_order": 57, "fileName": "Historia familia Panceri 3.jpg", "title": "História Família Panceri - Parte 3", "corroboration": "Terceira e última página do texto datilografado sobre a família Panceri. Foca na mudança de Joseph Panceri para o núcleo urbano de Caxias do Sul em 1909, a instalação de sua indústria de seda, a viagem à Europa para aquisição de maquinários modernos, a dedicação dos filhos à continuidade da tecelagem e o legado final de Joseph Panceri.", "admin_assigned_section": "Panceri", "tags": "família Panceri,história,Caxias do Sul,indústria,maquinário,legado,documento datilografado"}
    ]
}
# --- FIM DOS DADOS INICIAIS ---

def populate_database():
    app.logger.info("Iniciando a população do banco de dados (Timeline e Galeria)...")
    try:
        # Popular TimelineEvents
        for section_key, events_data_list in initial_data_to_seed.items():
            if section_key in ['panceri', 'pompeia', 'scavino']:
                app.logger.info(f"Processando seção da timeline: {section_key}")
                for event_data in events_data_list:
                    existing_event = TimelineEvent.query.filter_by(
                        title=event_data['title'], year=event_data.get('year'), section=section_key
                    ).first()
                    if not existing_event:
                        new_event = TimelineEvent(
                            section=section_key, sub_section=event_data.get('sub_section'),
                            year=event_data.get('year'), title=event_data['title'],
                            text=event_data['text'], images=event_data.get('images', []),
                            corroboration=event_data.get('corroboracao')
                        )
                        db.session.add(new_event)
        
        # Popular GalleryImages
        gallery_items_data = initial_data_to_seed.get('gallery_images', [])
        app.logger.info(f"Processando {len(gallery_items_data)} imagens da galeria.")
        for idx, image_data in enumerate(gallery_items_data):
            existing_image = GalleryImage.query.filter_by(file_name=image_data['fileName']).first()
            if not existing_image:
                new_image = GalleryImage(
                    chronological_order=image_data.get('chronological_order', idx + 1),
                    file_name=image_data['fileName'], title=image_data.get('title'),
                    corroboration_text=image_data.get('corroboration'),
                    admin_assigned_section=image_data.get('admin_assigned_section', 'Geral'),
                    tags=image_data.get('tags')
                )
                db.session.add(new_image)

        db.session.commit()
        app.logger.info("Banco de dados (Timeline e Galeria) populado/verificado com sucesso!")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro CRÍTICO ao popular o banco de dados: {e}", exc_info=True)

# --- Rotas de Autenticação ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            app.logger.info(f"Usuário '{username}' logado com sucesso.")
            next_page = request.args.get('next')
            if next_page and urlparse(next_page).netloc == '':
                return redirect(next_page)
            return redirect(url_for('admin.index'))
        else:
            app.logger.warning(f"Falha na tentativa de login para o usuário '{username}'.")
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    app.logger.info(f"Usuário '{current_user.username}' desconectado.")
    logout_user()
    flash('Você foi desconectado com sucesso.', 'info')
    return redirect(url_for('login'))

# --- Rotas da API ---
@app.route('/api/timeline/<section_name>', methods=['GET'])
def get_timeline_section(section_name):
    app.logger.info(f"API_TIMELINE: Req para seção: '{section_name}'")
    try:
        events_from_db = TimelineEvent.query.filter(TimelineEvent.section.ilike(section_name.lower())).order_by(TimelineEvent.year, TimelineEvent.id).all()
        app.logger.info(f"API_TIMELINE: {len(events_from_db)} eventos para '{section_name.lower()}'.")
        return jsonify([event.to_dict() for event in events_from_db])
    except Exception as e:
        app.logger.error(f"API_TIMELINE: Erro para '{section_name}': {e}", exc_info=True)
        return jsonify({"erro": "Erro interno na API da timeline."}), 500

@app.route('/api/gallery', methods=['GET'])
def get_gallery_images():
    app.logger.info("API_GALLERY: Req para galeria.")
    try:
        images_from_db = GalleryImage.query.order_by(GalleryImage.chronological_order, GalleryImage.id).all()
        app.logger.info(f"API_GALLERY: {len(images_from_db)} imagens encontradas.")
        return jsonify([image.to_dict() for image in images_from_db])
    except Exception as e:
        app.logger.error(f"API_GALLERY: Erro interno: {e}", exc_info=True)
        return jsonify({"erro": "Erro interno na API da galeria."}), 500

# --- Rota Principal ---
@app.route('/')
def index():
    app.logger.info("Rota principal '/' acessada.")
    return render_template('index.html')

# --- Inicialização ---
if __name__ == '__main__':
    with app.app_context():
        app.logger.info("Iniciando aplicação Flask...")
        db.create_all()
        app.logger.info("Banco de dados e tabelas verificados/criados.")
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin')
            admin_user.set_password(os.environ.get('ADMIN_PASSWORD', 'admin_pass_fallback_123!'))
            db.session.add(admin_user)
            db.session.commit()
            app.logger.info("Usuário 'admin' padrão criado/verificado. MUDE A SENHA PADRÃO!")
        
        if not TimelineEvent.query.first() or not GalleryImage.query.first():
            app.logger.info("Populando dados iniciais (Timeline e/ou Galeria)...")
            populate_database()
        else:
            app.logger.info("Timeline e Galeria já contêm dados.")

    app.logger.info("Iniciando servidor Flask em modo debug na porta 5000.")
    app.run(debug=True, host='0.0.0.0', port=5000)