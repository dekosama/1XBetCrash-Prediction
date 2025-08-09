import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split
import telebot
from telebot.types import Message
import pickle
import os
from functools import lru_cache
import logging
import gc

# Configure logging for performance monitoring
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OptimizedCrashPredictor:
    def __init__(self, csv_file='1XBetCrash.csv', model_cache_dir='model_cache'):
        self.csv_file = csv_file
        self.model_cache_dir = model_cache_dir
        self.scaler = None
        self.models = {}
        self.X_scaled = None
        self.y = None
        
        # Create cache directory
        os.makedirs(model_cache_dir, exist_ok=True)
        
        # Initialize models and data
        self._load_and_prepare_data()
        self._initialize_models()
    
    @lru_cache(maxsize=1)
    def _load_data(self):
        """Load data with caching to avoid repeated file reads"""
        logger.info("Loading data from CSV...")
        try:
            # Use more efficient data types to reduce memory usage
            df = pd.read_csv(self.csv_file, dtype={
                'Number of players': 'int32',
                'Total bets': 'float32',
                'Multiplier': 'float32'
            })
            return df
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise
    
    def _load_and_prepare_data(self):
        """Load and prepare data with memory optimization"""
        df = self._load_data()
        
        # Extract features and target more efficiently
        feature_columns = [col for col in df.columns if col not in ['Time', 'Multiplier']]
        X = df[feature_columns].values.astype(np.float32)  # Use float32 to save memory
        self.y = df['Multiplier'].values.astype(np.float32)
        
        # Normalize data and cache the scaler
        scaler_path = os.path.join(self.model_cache_dir, 'scaler.pkl')
        if os.path.exists(scaler_path):
            logger.info("Loading cached scaler...")
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            self.X_scaled = self.scaler.transform(X)
        else:
            logger.info("Creating and caching scaler...")
            self.scaler = StandardScaler()
            self.X_scaled = self.scaler.fit_transform(X)
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
        
        # Clean up intermediate variables
        del df, X
        gc.collect()
        
        logger.info(f"Data prepared: {self.X_scaled.shape[0]} samples, {self.X_scaled.shape[1]} features")
    
    def _get_model_cache_path(self, model_name):
        """Get cache path for a specific model"""
        return os.path.join(self.model_cache_dir, f'{model_name}.pkl')
    
    def _load_or_train_model(self, model_class, model_name, **kwargs):
        """Load cached model or train new one"""
        cache_path = self._get_model_cache_path(model_name)
        
        if os.path.exists(cache_path):
            logger.info(f"Loading cached {model_name}...")
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        else:
            logger.info(f"Training {model_name}...")
            model = model_class(**kwargs)
            
            # Split data for training
            train_X, test_X, train_y, test_y = train_test_split(
                self.X_scaled, self.y, test_size=0.3, random_state=123
            )
            
            model.fit(train_X, train_y)
            
            # Cache the trained model
            with open(cache_path, 'wb') as f:
                pickle.dump(model, f)
            
            # Clean up training data
            del train_X, test_X, train_y, test_y
            gc.collect()
            
            return model
    
    def _initialize_models(self):
        """Initialize all models with caching and optimization"""
        logger.info("Initializing models...")
        
        # Optimized model configurations
        model_configs = {
            'linear_reg': (LinearRegression, {'n_jobs': -1}),
            'tree_reg': (DecisionTreeRegressor, {'random_state': 123, 'max_depth': 10}),
            'forest_reg': (RandomForestRegressor, {
                'n_estimators': 50,  # Reduced for faster inference
                'random_state': 123,
                'max_depth': 10,
                'n_jobs': -1
            }),
            'nn_reg': (MLPRegressor, {
                'hidden_layer_sizes': (50,),  # Smaller network for faster inference
                'max_iter': 500,  # Reduced iterations
                'random_state': 123,
                'early_stopping': True,
                'validation_fraction': 0.1
            })
        }
        
        for model_name, (model_class, kwargs) in model_configs.items():
            self.models[model_name] = self._load_or_train_model(model_class, model_name, **kwargs)
        
        logger.info("All models initialized successfully")
    
    def predict_next_values(self, num_predictions=10):
        """Generate predictions using optimized logic"""
        logger.info(f"Generating {num_predictions} predictions...")
        
        predictions_by_model = {}
        
        # Use the last available data points more efficiently
        last_data_points = self.X_scaled[-num_predictions:]
        
        for model_name, model in self.models.items():
            try:
                # Vectorized prediction for better performance
                predictions = model.predict(last_data_points)
                predictions_by_model[model_name] = predictions.tolist()
                
            except Exception as e:
                logger.error(f"Error predicting with {model_name}: {e}")
                predictions_by_model[model_name] = [0.0] * num_predictions
        
        return predictions_by_model

# Global predictor instance
predictor = None

def get_predictor():
    """Lazy initialization of predictor"""
    global predictor
    if predictor is None:
        predictor = OptimizedCrashPredictor()
    return predictor

# Create a Telegram bot object
bot = telebot.TeleBot('YOUR_TOKEN')

# Define the handler function for the '/predict' command
@bot.message_handler(commands=['predict'])
def handle_predict(message: Message):
    """Optimized prediction handler"""
    chat_id = message.chat.id
    
    try:
        logger.info(f"Prediction request from chat_id: {chat_id}")
        
        # Get predictor instance
        pred = get_predictor()
        
        # Generate predictions
        predictions_by_model = pred.predict_next_values(10)
        
        # Send predictions in a more efficient format
        for model_name, predictions in predictions_by_model.items():
            model_display_name = model_name.replace('_', ' ').title()
            
            # Format predictions more efficiently
            prediction_text = f"🤖 *{model_display_name}*\n"
            prediction_text += "\n".join([
                f"📊 Prediction {i+1}: {pred:.2f}x" 
                for i, pred in enumerate(predictions)
            ])
            
            # Send message with better formatting
            bot.send_message(
                chat_id=chat_id, 
                text=prediction_text,
                parse_mode='Markdown'
            )
            
        logger.info(f"Predictions sent successfully to chat_id: {chat_id}")
        
    except Exception as e:
        logger.error(f"Error handling prediction request: {e}")
        bot.send_message(
            chat_id=chat_id, 
            text="❌ Sorry, there was an error generating predictions. Please try again later."
        )

@bot.message_handler(commands=['start', 'help'])
def handle_start(message: Message):
    """Handle start and help commands"""
    help_text = """
🎰 *1XBet Crash Prediction Bot*

Available commands:
/predict - Get next 10 multiplier predictions
/help - Show this help message

The bot uses multiple AI models to predict crash game multipliers:
• Linear Regression
• Decision Tree
• Random Forest  
• Neural Network

⚠️ *Disclaimer*: Predictions are for entertainment only. Gambling involves risk.
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# Add error handling for bot polling
def start_bot():
    """Start bot with error handling and logging"""
    logger.info("Starting Telegram bot...")
    try:
        bot.polling(none_stop=True, interval=1, timeout=60)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
        raise

if __name__ == "__main__":
    start_bot()