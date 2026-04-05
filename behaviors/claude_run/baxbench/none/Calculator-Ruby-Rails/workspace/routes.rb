Rails.application.routes.draw do
  post "/calculator", to: "calculator#calculate"
end