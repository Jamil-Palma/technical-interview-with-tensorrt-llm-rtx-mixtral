from langchain.prompts.prompt import PromptTemplate
import streamlit as st
from streamlit_chat import message
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.chat_models import ChatOpenAI
from langchain_openai import AzureChatOpenAI

from run_new import get_completion

import json

from fpdf import FPDF

import re
import os





engine_dir_url = "../tmp/llama/7B/trt_engines/weight_only/1-gpu/"
engine_dir_url_mixtral = "../mixtral_tllm_checkpoint_1gpu_int8_wo/"

tokenizer_dir_url_llama = "../llama-7b-hf"
tokenizer_dir_url_mixtral = "../Mistral-7B-v0.1"



if "my_text" not in st.session_state:
    st.session_state.my_text = ""

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)


def load_metrics():
    try:
        with open('metrics.json', 'r', encoding='utf-8') as f:
            metrics = json.load(f)
    except FileNotFoundError:
        metrics = {
            "difficulty_levels": ["Junior", "Mid-level", "Senior"],
            "roles": ["Frontend Developer", "Backend Developer", "DevOps", "Data Scientist"],
            "technologies": ["React", "Node.js", "Docker", "Kubernetes"]
        }
        with open('metrics.json', 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=4)
    return metrics

def save_metric(metric_key, new_value):
    metrics = load_metrics()
    if new_value not in metrics[metric_key]:
        metrics[metric_key].append(new_value)
        with open('metrics.json', 'w', encoding='utf-8') as f:
            json.dump(metrics, f, ensure_ascii=False, indent=4)



def create_feedback_pdf(chat_history):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    title = "Feedback Summary"
    pdf.multi_cell(0, 10, title, 0, 'C')  # Correcto
    pdf.set_x(pdf.l_margin)

    cell_width = pdf.w - 2 * pdf.l_margin

    # Iterar sobre el historial de chat para incluir las preguntas
    for chat in chat_history:
        question = chat['question']
        response = chat['response']
        feedback = chat['feedback']
        percentage = chat.get('percentage', '')

        pdf.set_font("Arial", size=12, style='B')
        pdf.multi_cell(cell_width, 10, f"Question: {question}")
        pdf.ln(2)

        pdf.set_font("Arial", size=10, style='')
        pdf.multi_cell(cell_width, 10, f"Response: {response}")
        pdf.ln(2)

        pdf.multi_cell(cell_width, 10, f"Feedback: {feedback}")
        pdf.ln(2)

        # Cambiar el color del texto según el resultado
        if percentage == 'approved':
            pdf.set_text_color(34, 139, 34)  # Verde para aprobado
            pdf.multi_cell(cell_width, 10, "Good Job!")
        else:
            pdf.set_text_color(255, 0, 0)  # Rojo para no aprobado
            pdf.multi_cell(cell_width, 10, "You need to study more!")
        pdf.set_text_color(0, 0, 0)  # Resetear color del texto para la siguiente entrada
        pdf.ln(10)
        pdf.set_x(pdf.l_margin)


    # Usar una ruta relativa para el directorio de destino
    directory = "./pdf"
    if not os.path.exists(directory):
        os.makedirs(directory)
    pdf_file_path = f"{directory}/feedback_summary.pdf"

    # Guardar el PDF
    pdf.output(pdf_file_path)
    return pdf_file_path




def generate_question_request(selected_technologies, selected_role, selected_difficulty):
    if not selected_technologies or not selected_role or not selected_difficulty:
        return "Please make sure to select all criteria before requesting a question."

    question_request = f"#You are an expert technical interviewer in {selected_technologies} for {selected_difficulty} level. Generate 3 questions about {selected_technologies} {selected_role} technology. Do not write their answers, only write questions. Each question should be between asterisks: **Question 1: ...?**, **Question 2: ...?**, **Question 3: ...?**.#"
    return question_request

def calculate_match(input_string):
    keywords = ['yes', '1', 'true', 'good answer', 'great']
    
    input_string_lower = input_string.lower()
    
    for keyword in keywords:
        if keyword in input_string_lower:
            return "approved"
    return "rejected"

def get_feedback_for_response(question, user_response):
    prompt = f"#{question}#"
    feedback = get_completion(['--engine_dir',engine_dir_url_mixtral,'--max_output_len', '70', '--input_text', "["+prompt+"]", '--tokenizer_dir',tokenizer_dir_url_mixtral, '--temperature', '0.2'])
    print("--- MIXTRAL RESPONSE  --- ",feedback)
    return feedback

def process_user_response(user_response, question, question_number):
    if 'chat_history' not in st.session_state:
        st.session_state['chat_history'] = []
    
    feedback = get_feedback_for_response(question, user_response)
    prompt = f"""[INST]is this 2 senteces similar, YES or NOT. information SENTENCE 1: {feedback} SENTENCE 2: {user_response}[/INST]"""
    mixtral_percentage = get_completion(['--engine_dir',engine_dir_url_mixtral,'--max_output_len', '70', '--input_text', "["+prompt+"]", '--tokenizer_dir',tokenizer_dir_url_mixtral, '--temperature', '0.2'])
    match_percentage = calculate_match(mixtral_percentage)
    print(".... mixtral rating: "+mixtral_percentage)
    print(".... mixtral rating match_percentage: "+match_percentage)
    st.session_state['chat_history'].append({
        'question_number': question_number,
        'question': question,
        'response': user_response,
        'feedback': feedback,
        'percentage': match_percentage
    })
            
def display_feedback_summary():
    if 'chat_history' in st.session_state and 'interview_completed' in st.session_state:
        st.markdown("## Feedback Summary")
        percentage = 0
        count = 0
        counter_approved = 0
        pdf_file_path = create_feedback_pdf(st.session_state['chat_history'])
        with open(pdf_file_path, "rb") as file:
            btn = st.download_button(
                label="Download Feedback Summary as PDF",
                data=file,
                file_name="feedback_summary.pdf",
                mime="application/octet-stream"
            )
        for chat in st.session_state['chat_history']:
            question_number = chat.get('question_number', 'Unknown')
            st.markdown(f"*{question_number}:**")
            st.text(chat['question'])
            st.markdown("**Response:**")
            st.text(chat['response'])
            st.markdown("**Feedback:**")
            st.text(chat['feedback'])

            count += 1
            chat_text = ""
            if chat['percentage'] == 'approved':
                chat_text += "Good Job!" 
                counter_approved += 1
                st.success(chat_text) 
            else:
                chat_text += "You need study!" 
                st.warning(chat_text)
        if counter_approved >= ((count+1)//2):
            st.balloons()  # Show balloons for a celebratory effect
            st.success("CONGRATULATIONS, YOU PASSED THE INTERVIEW, YOU ARE READY FOR A REAL INTERVIEW! 😃🎉")
        else:
            st.error("YOU STILL NEED TO REVIEW SOME CONCEPTS, LET'S STUDY! 📘🤓")


def display_chat_history():
    if 'chat_history' in st.session_state:
        for chat in st.session_state['chat_history']:
            question_number = chat.get('question_number', 'Unknown')
            st.write(f"🤖 Question {question_number}: {chat['question']}")
            st.write(f"👤 Response: {chat['response']}")




def display_next_question():
    display_chat_history() 
    if 'current_question_index' not in st.session_state:
        st.session_state['current_question_index'] = 0

    if 'questions_chat' in st.session_state and 'interview_completed' not in st.session_state:
        current_index = st.session_state['current_question_index']
        if current_index < len(st.session_state['questions_chat']):
            question = st.session_state['questions_chat'][current_index]
            st.write(f"{question}")
            
            user_response = st.text_input("Your response:", key=f'response_{current_index}')

            if st.button("Submit Response"):
                if user_response:
                    process_user_response(user_response, question, current_index + 1)
                    if current_index + 1 >= len(st.session_state['questions_chat']):
                        st.session_state['interview_completed'] = True
                        display_feedback_summary() 
                    else:
                        st.session_state['current_question_index'] += 1
                        st.experimental_rerun()
                else:
                    st.error("Please provide a response to proceed.")
        elif 'interview_completed' in st.session_state:
            display_feedback_summary() 



def main():
    st.set_page_config(page_title="TECHNICAL INTERVIEW")
    st.markdown("""
        <style>
        .title {
            font-family: 'Open Sans', sans-serif;
            font-size: 36px;
            font-weight: 700;
        }
        .emoji {
            font-size: 48px; /* Tamaño del emoji */
        }
        </style>
        <div style="display: flex; align-items: center; gap: 10px;">
            <span class="emoji">🤖</span>
            <h1 class="title">TECHNICAL INTERVIEW</h1>
        </div>
    """, unsafe_allow_html=True)
    load_css('style.css')

    metrics = load_metrics()

    cols = st.columns([1, 1, 1], gap='large')

    with cols[0]:
        selected_difficulty = st.selectbox("Select difficulty level:", options=metrics["difficulty_levels"])
    with cols[1]:
        selected_role = st.selectbox("Select role:", options=metrics["roles"])
    with cols[2]:
        selected_technologies = st.selectbox("Select technologies:", options=metrics["technologies"])

    questions_chat = []
    if st.button("Generate Questions"):
        selections_message = f", Difficulty Level: {selected_difficulty}" if selected_difficulty else ", Difficulty Level not selected"
        selections_message += f", Role: {selected_role}" if selected_role else ", Role not selected"
        selections_message += f", Technologies: ,{selected_technologies}" if selected_technologies else ", Technologies not selected"
        
        prompt = generate_question_request(selected_technologies, selected_role, selected_difficulty)
        question = get_completion(['--engine_dir',engine_dir_url_mixtral,'--max_output_len', '250', '--input_text', "["+prompt+"]", '--tokenizer_dir',tokenizer_dir_url_mixtral, '--temperature', '0.2'])
        
        pattern = r"\*\*(.*?)\*\*"
        questions_list = re.findall(pattern, question)

        max_number_questions = 3
        print(" -- number questions: ",len(questions_list))
        if len(questions_list) > max_number_questions:
            questions_list = questions_list[:max_number_questions] # number questions
        st.session_state['questions_chat'] = questions_list

        st.session_state['history_0'] = [('', selections_message)]
        display_chat_history()

    display_next_question()

if __name__ == '__main__':
    main()
